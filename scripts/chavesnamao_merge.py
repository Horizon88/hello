"""Merge chavesnamao Santa Catarina coastal land into listings.json."""
import json, math, re, statistics, sys
from collections import Counter

RAW = "/tmp/chavesnamao.json"
PATH = "/home/user/hello/docs/listings.json"
BRLUSD = 1 / 5.4
raw = json.load(open(RAW))
print(f"raw chavesnamao rows: {len(raw)}", file=sys.stderr)

# Santa Catarina coastline anchors
SC_COAST = [
    (-26.24,-48.64),(-26.90,-48.62),(-27.10,-48.55),(-27.28,-48.36),(-27.44,-48.40),
    (-27.60,-48.45),(-27.78,-48.50),(-27.99,-48.62),(-28.24,-48.65),(-28.50,-48.78),
    (-28.68,-48.99),(-26.78,-48.55),(-27.16,-48.50),
]
def hav(a,b,c,d):
    R=6371; dl=math.radians(c-a); dlo=math.radians(d-b)
    h=math.sin(dl/2)**2+math.cos(math.radians(a))*math.cos(math.radians(c))*math.sin(dlo/2)**2
    return 2*R*math.asin(math.sqrt(h))

FOREIGN_NOTE = ("Brazil: foreigners may own urban/titled land freely; rural land is "
                "capped/needs INCRA approval for larger areas, and land within 150 km of "
                "a land border needs security clearance. Verify título + georreferenciamento.")

PREMIUM = re.compile(r'jurere|campeche|praia|jardim|ponta|lagoa|santinho|ingleses|'
                     r'canasvieiras|rosa|mole|joaquina|brava|estaleiro', re.I)

existing = json.load(open(PATH))
existing = [e for e in existing if "src:chavesnamao" not in (e.get("rb","") or "")]
existing_urls = {e.get("u") for e in existing}

upms = [r["price_rm"]*BRLUSD/r["sqm"] for r in raw if r.get("price_rm") and r.get("sqm") and r["sqm"]>=100]
med = statistics.median(upms) if upms else 100

rows = []
for r in raw:
    brl = r.get("price_rm"); sqm = r.get("sqm")
    if not brl or not sqm or sqm < 100: continue
    if r.get("lat") is None: continue
    if r["url"] in existing_urls: continue
    usd = round(brl * BRLUSD)
    if usd < 5000: continue
    ac = round(sqm/4046.86, 3)
    upm = round(usd/sqm, 1)
    lat, lng = r["lat"], r["lng"]
    coast_km = round(min(hav(lat,lng,a,b) for a,b in SC_COAST), 1)

    rb = ["src:chavesnamao"]; score = 18; rb.append("base+18")
    b = -10 if ac<0.1 else -4 if ac<0.25 else 2 if ac<0.6 else 10 if ac<1.5 else 18 if ac<5 else 26
    score += b; rb.append(f"size{'+' if b>=0 else ''}{b}")
    ratio = upm/med if med else 1
    vb = 12 if ratio<0.5 else 7 if ratio<0.8 else 3 if ratio<1.0 else 0 if ratio<1.5 else -4 if ratio<2.5 else -8
    if vb: score += vb; rb.append(f"val{'+' if vb>0 else ''}{vb}")
    if coast_km <= 1: score += 18; rb.append("coast≤1km+18")
    elif coast_km <= 3: score += 11; rb.append("coast≤3km+11")
    elif coast_km <= 8: score += 5; rb.append("coast≤8km+5")
    nb = r.get("neighborhood","")
    prem = bool(PREMIUM.search(nb + " " + r.get("city","")))
    if prem: score += 6; rb.append("premium-beach+6")

    rows.append({
        "tp":"land", "cf":"Brazil", "r":round(score,1),
        "rg": r.get("city","Santa Catarina"), "a": nb[:40],
        "ac":ac, "m2":int(sqm), "usd":usd, "upm":upm,
        "v":"sea_view" if prem or coast_km<=1 else "coastal",
        "el":"", "t":"titled (verify)", "lat":lat, "lon":lng,
        "cur":"BRL", "lp":str(brl), "rb":"+".join(rb),
        "imgs":[], "u":r["url"], "name": f"Terreno {int(sqm)}m² · {nb}, {r.get('city','')} (SC)"[:180],
        "ski_km":None, "ski_r":"", "coast_km":coast_km,
        "foreign_note": FOREIGN_NOTE,
    })

merged = existing + rows
merged.sort(key=lambda x: x.get("r",0), reverse=True)
json.dump(merged, open(PATH,"w"), separators=(",",":"))
print(f"merged: {len(rows)} chavesnamao rows; total {len(merged)}", file=sys.stderr)
print("by city:", Counter(r["rg"] for r in rows).most_common(), file=sys.stderr)
