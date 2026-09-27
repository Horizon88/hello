"""Merge Redfin South Coast MA land into listings.json."""
import json, math, statistics, sys
from collections import Counter

RAW = "/tmp/redfin_ma.json"
PATH = "/home/user/hello/docs/listings.json"
raw = json.load(open(RAW))
print(f"raw redfin-ma rows: {len(raw)}", file=sys.stderr)

# South Coast MA coastline anchors (Buzzards Bay + Mount Hope Bay + Sakonnet)
COAST = [
    (41.509,-71.088),(41.545,-71.045),(41.575,-70.985),(41.590,-70.940),
    (41.628,-70.918),(41.638,-70.882),(41.660,-70.818),(41.700,-70.762),
    (41.745,-70.718),(41.704,-71.155),(41.600,-71.200),(41.520,-71.100),
    (41.552,-70.876),(41.665,-70.930),
]
def hav(a,b,c,d):
    R=6371; dl=math.radians(c-a); dlo=math.radians(d-b)
    h=math.sin(dl/2)**2+math.cos(math.radians(a))*math.cos(math.radians(c))*math.sin(dlo/2)**2
    return 2*R*math.asin(math.sqrt(h))

existing = json.load(open(PATH))
existing = [e for e in existing if "src:redfin-ma" not in (e.get("rb","") or "")]
existing_urls = {e.get("u") for e in existing}

upas = sorted((r["price_usd"]/r["acres"]) for r in raw if r.get("acres") and r["acres"]>=0.1)
med_upa = statistics.median(upas) if upas else 100000

rows = []
for r in raw:
    usd = r.get("price_usd"); ac = r.get("acres")
    if not usd or not ac or ac < 0.1: continue
    if r["url"] in existing_urls: continue
    m2 = int(ac*4046.86)
    upm = round(usd/m2, 1)
    lat, lng = r["lat"], r["lng"]
    coast_km = round(min(hav(lat,lng,a,b) for a,b in COAST), 2)

    rb = ["src:redfin-ma"]; score = 22; rb.append("base+22")
    b = -8 if ac<0.25 else 0 if ac<0.5 else 8 if ac<1 else 16 if ac<3 else 24 if ac<10 else 32
    score += b; rb.append(f"size{'+' if b>=0 else ''}{b}")
    upa = usd/ac
    ratio = upa/med_upa if med_upa else 1
    vb = 12 if ratio<0.4 else 7 if ratio<0.7 else 3 if ratio<1.0 else 0 if ratio<1.6 else -4 if ratio<2.6 else -8
    if vb: score += vb; rb.append(f"val{'+' if vb>0 else ''}{vb}")
    if coast_km <= 0.2: score += 22; rb.append("waterfront+22")
    elif coast_km <= 1: score += 14; rb.append("coast≤1km+14")
    elif coast_km <= 3: score += 7; rb.append("coast≤3km+7")
    dom = r.get("dom")
    if dom and dom >= 365: score += 8; rb.append("stale>1yr+8")

    rows.append({
        "tp":"land", "cf":"USA", "r":round(score,1),
        "rg":"Massachusetts", "a": (r.get("city") or "")[:40],
        "ac":ac, "m2":m2, "usd":usd, "upm":upm,
        "v":"waterfront" if coast_km<=0.2 else ("sea_visible" if coast_km<=1.5 else ""),
        "el":"", "t":"", "lat":lat, "lon":lng,
        "cur":"USD", "lp":str(usd), "rb":"+".join(rb),
        "imgs":[], "u":r["url"],
        "name": (f"{r.get('address','')}, {r.get('city','')} MA" ).strip(", ")[:180],
        "ski_km":None, "ski_r":"", "coast_km":coast_km,
        "days_on_market": int(dom) if dom else None,
    })

merged = existing + rows
merged.sort(key=lambda x: x.get("r",0), reverse=True)
json.dump(merged, open(PATH,"w"), separators=(",",":"))
print(f"merged: {len(rows)} redfin-ma rows; total {len(merged)}", file=sys.stderr)
print("by city:", Counter(r["a"] for r in rows).most_common(12), file=sys.stderr)
print("waterfront (≤0.2km):", sum(1 for r in rows if (r['coast_km'] or 9)<=0.2), file=sys.stderr)
