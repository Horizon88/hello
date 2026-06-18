"""Open a GitHub issue for each official source that CHANGED this run.

Run after check.py. Reads data/changes.json. Uses GITHUB_TOKEN +
GITHUB_REPOSITORY from the Actions environment; a no-op when run locally
without them.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
MAX_DIFF_CHARS = 5000  # keep issue bodies readable


def gh_post(repo: str, token: str, title: str, body: str, labels: list[str]) -> dict:
    url = f"https://api.github.com/repos/{repo}/issues"
    data = json.dumps({"title": title, "body": body, "labels": labels}).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "regwatch",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        print("GITHUB_TOKEN / GITHUB_REPOSITORY missing — running locally?", file=sys.stderr)
        return 0

    changes_path = DATA / "changes.json"
    if not changes_path.exists():
        print("no changes.json — nothing to do")
        return 0
    changes = json.loads(changes_path.read_text())
    if not changes:
        print("no regulation changes this run")
        return 0

    today = dt.date.today().isoformat()
    for c in changes:
        title = f"[regwatch] {c['area']}: official page changed — {c['title']}"
        diff = c.get("diff", "")
        truncated = ""
        if len(diff) > MAX_DIFF_CHARS:
            diff = diff[:MAX_DIFF_CHARS]
            truncated = "\n… (diff truncated — see data/snapshots in git for the full change)"
        body = (
            f"An official source page for **{c['area']}** changed.\n\n"
            f"- **Source:** [{c['title']}]({c['url']})\n"
            f"- **Detected:** {today}\n"
            f"- **Snapshot:** `data/snapshots/{c['id']}.txt`\n\n"
            f"⚠️ Automated diff of the page text (verify against the live page before acting):\n\n"
            f"```diff\n{diff}{truncated}\n```\n"
        )
        labels = ["regulation-change", c.get("label", "regwatch")]
        try:
            issue = gh_post(repo, token, title, body, labels)
            print(f"opened issue #{issue.get('number')} for {c['id']}")
        except urllib.error.HTTPError as e:
            print(f"HTTPError opening issue for {c['id']}: {e.code} {e.reason}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"error opening issue for {c['id']}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
