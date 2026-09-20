"""Merge realtor.com/international land into listings.json (Grenada, etc.).

Island markets: virtually all land is near coast, so we compute a coast
distance from a coarse Grenada outline and bonus accordingly. Region = parish
parsed from the address. Adds the foreign-ownership note (Grenada requires an
Alien Landholding Licence for non-nationals).
"""
import json, math, re, statistics, sys
from collections import Counter

RAW = "/tmp/realtor_intl.json"
PATH = "/home/user/hello/docs/listings.json"
raw = json.load(open(RAW))
print(f"raw realtor-intl rows: {len(raw)}", file=sys.stderr)

# coarse Grenada coastline anchors (main island) for a coast-distance estimate
GRENADA_COAST = [
    (12.007,-61.786),(12.050,-61.770),(12.120,-61.768),(12.190,-61.740),
    (12.223,-61.690),(12.210,-61.615),(12.160,-61.600),(12.100,-61.610),
    (12.030,-61.650),(11.995,-61.700),(11.985,-61.758),(12.007,-61.786),
]
def hav(a,b,c,d):
    R=6371; dl=math.radians(c-a); dlo=math.radians(d-b)
    h=math.sin(dl/2)**2+math.cos(math.radians(a))*math.cos(math.radians(c))*math.sin(dlo/2)**2
    return 2*R*math.asin(math.sqrt(h))

FOREIGN_NOTE = ("Grenada: non-nationals need an Alien Landholding Licence (ALHL) "
                "to hold land — budget ~10% of price + legal; also a route to "
                "Citizenship-by-Investment on approved real estate.")

def parish(addr):
    m = re.search(r'\b(?:St\.?|Saint)\s+([A-Za-z]+)', addr or "")
    if m:
        return "St. " + m.group(1).capitalize()
    return "Grenada"

def sea_view(addr):
    return bool(re.search(r'beach|anse|epines|bay|point|sea|ocean|calivigny|sauteurs', addr or "", re.I))

existing = json.load(open(PATH))
existing = [e for e in existing if "src:realtor-intl" not in (e.get("rb","") or "")]
existing_urls = {e.get("u") for e in existing}

upms = [r["usd"]/(r["sqft"]*0.092903) for r in raw if r.get("usd") and r.get("sqft")]
med = statistics.median(upms) if upms else 100

rows = []
for r in raw:
    usd = r.get("usd"); sqft = r.get("sqft")
    if not usd or not sqft or sqft < 400: continue
    if r["url"] in existing_urls: continue
    sqm = sqft * 0.092903
    ac = round(sqft/43560, 3)
    upm = round(usd/sqm, 1)
    lat, lng = r["lat"], r["lng"]
    coast_km = round(min(hav(lat,lng,a,b) for a,b in GRENADA_COAST), 2)

    rb = ["src:realtor-intl"]; score = 18; rb.append("base+18")
    # size (island lots are small; reward the rare larger parcels)
    b = -8 if ac<0.25 else 0 if ac<0.5 else 8 if ac<1 else 16 if ac<3 else 26 if ac<10 else 34
    score += b; rb.append(f"size{'+' if b>=0 else ''}{b}")
    ratio = upm/med if med else 1
    vb = 12 if ratio<0.5 else 7 if ratio<0.8 else 3 if ratio<1.0 else 0 if ratio<1.5 else -4 if ratio<2.5 else -8
    if vb: score += vb; rb.append(f"val{'+' if vb>0 else ''}{vb}")
    if coast_km <= 0.4: score += 20; rb.append("beachfront+20")
    elif coast_km <= 1: score += 14; rb.append("coast≤1km+14")
    elif coast_km <= 3: score += 8; rb.append("coast≤3km+8")

    rows.append({
        "tp":"land", "cf":"Grenada", "r":round(score,1),
        "rg": parish(r.get("addr")), "a": (r.get("addr") or "")[:40],
        "ac":ac, "m2":int(sqm), "usd":usd, "upm":upm,
        "v":"sea_view" if sea_view(r.get("addr")) else "coastal",
        "el":"", "t":"freehold (ALHL for foreigners)", "lat":lat, "lon":lng,
        "cur":"USD", "lp":str(usd), "rb":"+".join(rb),
        "imgs":[], "u":r["url"], "name": (r.get("addr") or "Grenada land")[:180],
        "ski_km":None, "ski_r":"", "coast_km":coast_km,
        "foreign_note": FOREIGN_NOTE,
    })

merged = existing + rows
merged.sort(key=lambda x: x.get("r",0), reverse=True)
json.dump(merged, open(PATH,"w"), separators=(",",":"))
print(f"merged: {len(rows)} realtor-intl rows; total {len(merged)}", file=sys.stderr)
print("by country/parish:", Counter((r["cf"],r["rg"]) for r in rows).most_common(), file=sys.stderr)
