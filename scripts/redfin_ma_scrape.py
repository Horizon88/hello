"""Redfin — South Coast Massachusetts land (Buzzards Bay / Mount Hope Bay).

The Land.com network (landsearch/landwatch/landandfarm) now 403s, and
realtor.com rate-limits, but Redfin's gis-csv export is open and accepts a
geographic polygon — so we pull vacant land for the South Coast region in one
CSV (no region-id hunting). The CSV carries address, price, LOT SIZE (sqft),
lat/lng and the listing URL. Emits /tmp/redfin_ma.json for the merge.

South Coast MA = the Buzzards Bay + Mount Hope Bay mainland coast: Seekonk,
Swansea, Somerset, Fall River, Westport, Dartmouth, New Bedford, Acushnet,
Fairhaven, Mattapoisett, Marion, Rochester, Wareham (west of the Cape Cod
Canal; the Cape/islands are excluded).
"""
import csv, io, json, subprocess, sys, urllib.parse

RELAY = "https://landrelay.flag-theory.workers.dev"
OUT = "/tmp/redfin_ma.json"

# lng lat pairs — RI border (Seekonk/Swansea) east to Wareham, coast to inland
POLY = "-71.38 41.45,-70.66 41.45,-70.66 41.90,-71.38 41.90,-71.38 41.45"
UUIPT = "5"          # 5 = vacant land

def relay(url, timeout=40):
    try:
        return subprocess.run(["curl", "-sk", "--compressed", "-m", str(timeout),
                               f"{RELAY}/?url={urllib.parse.quote(url, safe='')}"],
                              capture_output=True, text=True, timeout=timeout + 5).stdout
    except Exception:
        return ""

def pull(uipt):
    url = ("https://www.redfin.com/stingray/api/gis-csv?al=1&num_homes=350"
           "&ord=redfin-recommended-asc&page_number=1&sf=1,2,3,5,6,7&status=9"
           f"&uipt={uipt}&v=8&market=boston&poly={urllib.parse.quote(POLY)}")
    body = relay(url)
    # strip the MLS-rules note line if present, keep the real CSV
    lines = [l for l in body.splitlines() if l and not l.startswith('"In accordance')]
    if not lines:
        return []
    rows = list(csv.DictReader(io.StringIO("\n".join(lines))))
    return rows

def num(x):
    try: return float(str(x).replace(",", ""))
    except Exception: return None

if __name__ == "__main__":
    out = {}
    rows = pull(UUIPT)
    print(f"redfin CSV rows: {len(rows)}", file=sys.stderr)
    for r in rows:
        url = r.get("URL (SEE https://www.redfin.com/buy-a-home/comparative-market-analysis FOR INFO ON PRICING)") \
              or next((v for k, v in r.items() if k.startswith("URL")), None)
        price = num(r.get("PRICE"))
        lot = num(r.get("LOT SIZE"))           # sq ft for land
        lat = num(r.get("LATITUDE")); lng = num(r.get("LONGITUDE"))
        ptype = (r.get("PROPERTY TYPE") or "").strip()
        state = (r.get("STATE OR PROVINCE") or "").strip()
        if not (url and price and lat and lng): continue
        if "land" not in ptype.lower(): continue
        if state != "MA": continue            # South Coast Massachusetts only (poly clips into RI)
        if url.startswith("/"): url = "https://www.redfin.com" + url
        out[url] = {
            "url": url, "price_usd": int(price),
            "sqft_lot": lot, "acres": round(lot/43560, 3) if lot else None,
            "lat": lat, "lng": lng,
            "address": (r.get("ADDRESS") or "").strip(),
            "city": (r.get("CITY") or "").strip(), "zip": (r.get("ZIP OR POSTAL CODE") or "").strip(),
            "state": state, "dom": num(r.get("DAYS ON MARKET")),
            "ptype": ptype,
        }
    json.dump(list(out.values()), open(OUT, "w"))
    coord = sum(1 for r in out.values() if r.get("lat"))
    sized = sum(1 for r in out.values() if r.get("acres"))
    print(f"TOTAL {len(out)} South Coast MA land ({coord} coord, {sized} sized) -> {OUT}", file=sys.stderr)
    from collections import Counter
    print("by city:", Counter(r["city"] for r in out.values()).most_common(15), file=sys.stderr)
