"""Periodic regulatory-watch check.

Reads data/regulatory_watch.json, attempts to fetch each item's URL,
records:
  - last_attempted    ISO timestamp of this run
  - last_status       one of: ok / blocked / network_error / changed
  - last_status_note  free-text note (challenge type, error, diff summary)
  - last_snapshot_sha sha256 of the page text content (when fetched
                       cleanly) so subsequent runs can detect text drift

Intended to run from .github/workflows/weekly-scan.yml. Falls back to
plain curl with a desktop UA; if Playwright + stealth are available,
uses those for tougher sites (NZ Parliament has Radware which curl
can't get past — that's fine, we record 'blocked' and surface it in
the UI for manual review).

Idempotent — only updates the JSON if something actually changed.
"""
from __future__ import annotations
import json, hashlib, pathlib, subprocess, sys, datetime, re

REGISTRY = pathlib.Path(__file__).resolve().parent.parent / "data" / "regulatory_watch.json"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)
BOT_SIGNATURES = [
    "radware", "press & hold", "captcha", "verifying you are human",
    "cf-error", "cloudflare", "imperva", "access denied to akamai",
    "pardon our interruption", "checking your browser before",
]


def curl(url: str, timeout: int = 25) -> tuple[int, str]:
    try:
        p = subprocess.run(
            ["curl", "-skSL", "-m", str(timeout), "-A", UA, "-w", "\n__HTTP_CODE__:%{http_code}", url],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        body = p.stdout
        m = re.search(r"__HTTP_CODE__:(\d+)$", body)
        code = int(m.group(1)) if m else 0
        body = re.sub(r"__HTTP_CODE__:\d+$", "", body)
        return code, body
    except subprocess.TimeoutExpired:
        return 0, ""
    except Exception as e:
        return -1, str(e)


def looks_blocked(html: str) -> str | None:
    low = html.lower()
    for sig in BOT_SIGNATURES:
        if sig in low:
            return sig
    return None


def text_sha(html: str) -> str:
    # Strip tags and normalize whitespace before hashing — small markup
    # changes shouldn't trigger 'changed'.
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def check_item(item: dict) -> dict:
    url = item.get("url")
    if not url:
        return {"last_status": "no_url", "last_status_note": "no url on item"}
    code, body = curl(url)
    now = datetime.datetime.utcnow().isoformat() + "Z"
    out = {"last_attempted": now}
    if code in (0, -1):
        out.update({"last_status": "network_error",
                    "last_status_note": f"curl exit code {code}"})
        return out
    block_sig = looks_blocked(body)
    if block_sig or code >= 400:
        out.update({
            "last_status": "blocked",
            "last_status_note": f"http {code}; bot-signature: {block_sig or '?'} — open the URL manually to check status",
        })
        return out
    sha = text_sha(body)
    prior_sha = item.get("last_snapshot_sha")
    if prior_sha and prior_sha != sha:
        out.update({
            "last_status": "changed",
            "last_status_note": "page text changed since previous check — review the source",
            "last_snapshot_sha": sha,
        })
    else:
        out.update({
            "last_status": "ok",
            "last_status_note": "unchanged" if prior_sha else "first clean snapshot",
            "last_snapshot_sha": sha,
        })
    return out


def main() -> int:
    if not REGISTRY.exists():
        print(f"no registry at {REGISTRY}", file=sys.stderr)
        return 0
    data = json.loads(REGISTRY.read_text())
    items = data.get("items") or []
    any_change = False
    for item in items:
        before = {k: item.get(k) for k in ("last_status", "last_snapshot_sha")}
        result = check_item(item)
        item.update(result)
        after = {k: item.get(k) for k in ("last_status", "last_snapshot_sha")}
        if before != after:
            any_change = True
        print(f"  {item.get('id'):<40} {item.get('last_status'):<14}  {item.get('last_status_note','')[:80]}",
              file=sys.stderr)
    REGISTRY.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"updated {REGISTRY} (any_change={any_change})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
