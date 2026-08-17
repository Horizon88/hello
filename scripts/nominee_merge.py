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
    r["nominee"] = nom
    r["leverage"] = min(100, rec["n"] + rec.get("e", 0))
    flagged += 1
    if rec.get("e", 0) >= 15:
        lever += 1

json.dump(d, open("/home/user/hello/docs/listings.json", "w"), separators=(",", ":"))
print(f"flagged {flagged} nominee rows ({lever} with active exit pressure)", file=sys.stderr)
hits = Counter(h for r in d if r.get("nominee") for h in r["nominee"]["hits"])
print("signal counts:", hits.most_common(), file=sys.stderr)
rg = Counter(r["rg"] for r in d if r.get("nominee"))
print("by region:", rg.most_common(10), file=sys.stderr)
