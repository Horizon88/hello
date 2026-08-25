"""Merge nominee-scan results into listings.json.

Adds to flagged Thai rows:
  nominee:  {n, e, hits, own, excerpt?}   evidence bundle
  leverage: 0-100                          n + e, capped

n >= 20 is the flag threshold. 'company-only-transfer' (the FazWaz
structured Land Ownership field offering ONLY a company/share route) is the
strongest single signal that the land sits in a foreigner-controlled Thai
company — a legally-exposed structure whose seller cannot hold out.
"""
import json, sys
from collections import Counter

scan = json.load(open("/tmp/nominee_scan.json"))
d = json.load(open("/home/user/hello/docs/listings.json"))

# idempotency: clear previous nominee fields
for r in d:
    r.pop("nominee", None)
    r.pop("leverage", None)

flagged = lever = 0
for r in d:
    rec = scan.get(r.get("u") or "")
    if not rec or not rec.get("ok") or rec.get("n", 0) < 20:
        continue
    nom = {"n": rec["n"], "e": rec.get("e", 0), "hits": rec.get("hits", []),
           "own": rec.get("own", "")}
    if rec.get("excerpt"):
        nom["excerpt"] = rec["excerpt"][:300]
    # enrichment: deed quality, staleness, recent-bump
    stale = 0
    dom = rec.get("dom")
    if dom:
        nom["dom"] = dom
        nom["listed"] = rec.get("listed", "")
        if dom > 730: stale = 20
        elif dom > 365: stale = 10
        upd = (rec.get("updated") or "").lower()
        if stale and any(k in upd for k in ("day", "week")):
            stale += 5  # stale listing the seller is still actively bumping
            nom["hits"] = nom["hits"] + ["stale-but-bumping"]
    if rec.get("updated"):
        nom["updated"] = rec["updated"]
    deed = rec.get("deed", "")
    if deed:
        nom["deed"] = deed
        if "chanote" in deed.lower():
            stale += 5  # clean underlying title → clean transfer-out possible
    r["nominee"] = nom
    r["leverage"] = min(100, rec["n"] + rec.get("e", 0) + stale)
    flagged += 1
    if rec.get("e", 0) >= 15 or stale >= 15:
        lever += 1

json.dump(d, open("/home/user/hello/docs/listings.json", "w"), separators=(",", ":"))
print(f"flagged {flagged} nominee rows ({lever} with active exit pressure)", file=sys.stderr)
hits = Counter(h for r in d if r.get("nominee") for h in r["nominee"]["hits"])
print("signal counts:", hits.most_common(), file=sys.stderr)
rg = Counter(r["rg"] for r in d if r.get("nominee"))
print("by region:", rg.most_common(10), file=sys.stderr)
