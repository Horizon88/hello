"""Fetch every official source in sources.json, normalise it to stable,
line-oriented text, snapshot it into data/snapshots/, and detect changes
against the previous snapshot.

Outputs:
  data/snapshots/<id>.txt  — latest normalised text (committed → git keeps history + diffs)
  data/state.json          — per-source {hash, fetched_at, last_changed, status, error}
  data/changes.json        — sources that CHANGED this run (consumed by notify.py)
  data/STATUS.md           — human-readable at-a-glance table

Standard library only. The fetcher is deliberately conservative: a transient
network/HTTP error is recorded as a status but is NOT treated as a content
change, so we never alert just because a site was briefly down.
"""
from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SNAP_DIR = DATA / "snapshots"
SOURCES_FILE = ROOT / "sources.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 regwatch/1.0"
)

# Tags whose contents are never meaningful page text.
_SKIP_TAGS = {"script", "style", "noscript", "head", "svg", "template", "iframe"}
# Block-level tags that should force a line break in the extracted text.
_BLOCK_TAGS = {
    "p", "div", "br", "li", "ul", "ol", "tr", "td", "th", "table", "thead",
    "tbody", "section", "article", "header", "footer", "nav", "main", "aside",
    "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "dt", "dd", "dl",
}

# Volatile substrings stripped from EVERY source before hashing, so routine
# churn (timestamps, build hashes, "date modified" footers, CSRF nonces…)
# does not masquerade as a regulation change.
_GLOBAL_STRIP = [
    re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?"),
    re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\s?(AM|PM|am|pm)?\b"),
    re.compile(r"(?i)date modified:\s*\S+"),
    re.compile(r"(?i)last (updated|modified)[:\s]*\S.*"),
    re.compile(r"(?i)©\s*\d{4}([-–]\d{4})?"),
    re.compile(r"\b[0-9a-fA-F]{16,}\b"),          # long hex / build hashes
    re.compile(r"\b\d{10,}\b"),                    # long digit runs (epochs, ids)
    re.compile(r"(?i)(csrf|nonce|token|_ga|sessionid)[=:]\s*\S+"),
]


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def normalise(html: str, extra_strip: list[str] | None = None) -> str:
    """HTML -> stable, line-oriented plain text suitable for hashing & diffing."""
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        # Malformed markup: fall back to a crude tag strip rather than crashing.
        parser._parts = [re.sub(r"<[^>]+>", " ", html)]

    text = parser.text()
    for pat in _GLOBAL_STRIP:
        text = pat.sub("", text)
    for raw in extra_strip or []:
        try:
            text = re.sub(raw, "", text)
        except re.error:
            pass

    lines: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"[ \t ]+", " ", raw_line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines) + "\n"


def fetch(url: str, timeout: int = 30, retries: int = 3) -> str:
    """GET a URL with a browser-ish UA and simple backoff. Raises on failure."""
    import time

    last_err: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="replace")
        except Exception as e:  # noqa: BLE001 — retry any transport/HTTP error
            last_err = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise last_err if last_err else RuntimeError("unknown fetch error")


def _iter_sources(config: dict):
    for area in config.get("areas", []):
        for src in area.get("sources", []):
            yield area, src


def main() -> int:
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    config = json.loads(SOURCES_FILE.read_text())

    state_path = DATA / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}

    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    changes: list[dict] = []

    for area, src in _iter_sources(config):
        sid = src["id"]
        prev = state.get(sid, {})
        snap_file = SNAP_DIR / f"{sid}.txt"

        try:
            html = fetch(src["url"])
            text = normalise(html, src.get("strip"))
        except Exception as e:  # noqa: BLE001
            # Keep last good snapshot; just record the error. No alert.
            state[sid] = {
                **prev,
                "fetched_at": now,
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
            }
            print(f"[error] {sid}: {e}", file=sys.stderr)
            continue

        new_hash = hashlib.sha256(text.encode()).hexdigest()
        old_hash = prev.get("hash")
        old_text = snap_file.read_text() if snap_file.exists() else ""

        if old_hash is None:
            status = "baseline"
        elif new_hash != old_hash:
            status = "changed"
            diff = "".join(
                difflib.unified_diff(
                    old_text.splitlines(keepends=True),
                    text.splitlines(keepends=True),
                    fromfile=f"{sid} (previous)",
                    tofile=f"{sid} (current)",
                    n=2,
                )
            )
            changes.append({
                "id": sid,
                "title": src["title"],
                "url": src["url"],
                "area": area["area"],
                "label": area["label"],
                "diff": diff,
                "changed_at": now,
            })
        else:
            status = "unchanged"

        snap_file.write_text(text)
        state[sid] = {
            "area": area["area"],
            "title": src["title"],
            "url": src["url"],
            "hash": new_hash,
            "fetched_at": now,
            "last_changed": now if status in ("baseline", "changed") else prev.get("last_changed"),
            "status": status,
            "error": None,
        }
        print(f"[{status}] {sid}")

    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    (DATA / "changes.json").write_text(json.dumps(changes, indent=2) + "\n")
    _write_status_md(config, state)

    print(f"\n{len(changes)} change(s) this run.")
    return 0


def _write_status_md(config: dict, state: dict) -> None:
    lines = [
        "# regwatch — current status",
        "",
        f"_Last run: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}_",
        "",
        "| Area | Source | Status | Last changed | Last checked |",
        "|---|---|---|---|---|",
    ]
    for area, src in _iter_sources(config):
        st = state.get(src["id"], {})
        status = st.get("status", "—")
        if status == "error":
            status = "⚠️ error"
        lines.append(
            f"| {area['area']} | [{src['title']}]({src['url']}) | {status} | "
            f"{(st.get('last_changed') or '—')[:10]} | {(st.get('fetched_at') or '—')[:10]} |"
        )
    (DATA / "STATUS.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
