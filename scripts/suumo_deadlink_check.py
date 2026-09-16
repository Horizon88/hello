"""SUUMO dead-link pruner.

SUUMO listings expire ('掲載が終了' — listing ended) and 404, but the scraper
only ever ADDS rows, so dead links pile up in the inventory. This re-checks
SUUMO detail URLs and removes only DEFINITIVELY dead ones.

Safety: a row is pruned only on a definitive signal —
  HTTP 404, OR (body has '掲載が終了'/'お探しの' AND lacks '販売価格').
A network failure / timeout / empty body NEVER prunes (fail-safe: keep).

Cron-friendly: checks the CAP least-recently-checked rows per run, tracking
last-check time in /tmp/suumo_checked.json, so repeated runs rotate through
the whole set without hammering SUUMO.

Usage:  python3 scripts/suumo_deadlink_check.py [CAP]   (default CAP=1500)
"""
import json, subprocess, sys, time
from datetime import date

PATH = "/home/user/hello/docs/listings.json"
CACHE = "/tmp/suumo_checked.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
CAP = int(sys.argv[1]) if len(sys.argv) > 1 else 1500

def check(url, timeout=20):
    """Return 'dead', 'alive', or 'unknown' (never prune on unknown)."""
    cmd = ["curl", "-sL", "-m", str(timeout), "-A", UA,
           "-H", "Accept-Language: ja,en;q=0.8", "-H", "Referer: https://suumo.jp/",
           "-w", "\n@@HTTP%{http_code}@@", url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    except Exception:
        return "unknown"
    body = r.stdout or ""
    code = ""
    if "@@HTTP" in body:
        code = body.rsplit("@@HTTP", 1)[-1].strip("@")
        body = body.rsplit("\n@@HTTP", 1)[0]
    if code == "404":
        return "dead"
    if not body or len(body) < 2000:
        return "unknown"
    dead_sig = ("掲載が終了" in body) or ("お探しの" in body and "ご覧いただけません" in body)
    if dead_sig and "販売価格" not in body:
        return "dead"
    if "販売価格" in body or "土地面積" in body:
        return "alive"
    return "unknown"

def main():
    d = json.load(open(PATH))
    try:
        checked = json.load(open(CACHE))
    except Exception:
        checked = {}
    suumo = [r for r in d if "suumo.jp" in (r.get("u") or "")]
    # oldest-checked first (never-checked sorts first)
    suumo.sort(key=lambda r: checked.get(r["u"], ""))
    batch = suumo[:CAP]
    print(f"{len(suumo)} SUUMO rows; checking {len(batch)} (oldest-checked first)", file=sys.stderr)

    today = date.today().isoformat()
    dead_urls = set()
    dead = alive = unknown = 0
    for i, r in enumerate(batch):
        st = check(r["u"])
        if st == "dead":
            dead_urls.add(r["u"]); dead += 1
        elif st == "alive":
            alive += 1
        else:
            unknown += 1
        checked[r["u"]] = today
        if (i + 1) % 100 == 0:
            json.dump(checked, open(CACHE, "w"))
            print(f"  {i+1}/{len(batch)} · dead {dead} alive {alive} unknown {unknown}", file=sys.stderr)
        time.sleep(0.35)

    json.dump(checked, open(CACHE, "w"))
    if dead_urls:
        before = len(d)
        d = [r for r in d if r.get("u") not in dead_urls]
        json.dump(d, open(PATH, "w"), separators=(",", ":"))
        print(f"PRUNED {before - len(d)} dead SUUMO listings (dead {dead}, alive {alive}, unknown {unknown}); total now {len(d)}", file=sys.stderr)
    else:
        print(f"no dead links found this batch (alive {alive}, unknown {unknown})", file=sys.stderr)

if __name__ == "__main__":
    main()
