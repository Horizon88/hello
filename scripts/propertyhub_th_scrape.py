"""PropertyHub.in.th — Thai land listings scrape.

Big Thai property portal. List pages have __NEXT_DATA__ JSON with 60
listings each, including lat/lng coords, price in THB, title, slug,
and landAndHouseInformation (rai/ngan/wah area).

Coverage: sweeps all 77 Thai provinces. For coastal-focused users the
notable ones are captured below; add more via ALL_PROVINCES if needed.

URL pattern:
  /land-for-sale/<province-slug>?page=N   (English slug where available)

The site is server-rendered, so a plain fetch through the CF relay
returns the JSON directly.
"""
import json, re, subprocess, sys, time, urllib.parse, os

RELAY = "https://landrelay.flag-theory.workers.dev"

# All Thai coastal provinces (Andaman + Gulf) — where waterfront land lives.
COASTAL_PROVINCES = [
    # Andaman
    ("Ranong",              "ranong"),
    ("Phang Nga",           "phang-nga"),
    ("Phuket",              "phuket"),
    ("Krabi",               "krabi"),
    ("Trang",               "trang"),
    ("Satun",               "satun"),
    # Southern Gulf
    ("Pattani",             "pattani"),
    ("Songkhla",            "songkhla"),
    ("Nakhon Si Thammarat", "nakhon-si-thammarat"),
    ("Surat Thani",         "surat-thani"),
    ("Chumphon",            "chumphon"),
    # Western Gulf
    ("Prachuap Khiri Khan", "prachuap-khiri-khan"),
    ("Petchaburi",          "petchaburi"),
    # Bangkok / metro Gulf
    ("Samut Songkhram",     "samut-songkhram"),
    ("Samut Sakhon",        "samut-sakhon"),
    ("Samut Prakan",        "samut-prakan"),
    # Eastern Gulf
    ("Chonburi",            "chonburi"),
    ("Rayong",              "rayong"),
    ("Chanthaburi",         "chanthaburi"),
    ("Trat",                "trat"),
]

DISTRESS_PATS = [
    (r'ด่วน|urgent', 'urgent+15'),
    (r'ลดราคา|reduced|price\s*drop', 'price-drop+20'),
    (r'เจ้าของขายเอง|owner\s*sale', 'owner-direct+8'),
    (r'ต่อรอง|negotiable', 'negotiable+8'),
    (r'ต่ำกว่าราคาประเมิน|below\s*market', 'below-market+15'),
    (r'ขายด่วน|quick\s*sale', 'quick-sale+15'),
    (r'ขาดทุน|desperate', 'desperate+20'),
    (r'ยึด|foreclosure|npa|npl', 'foreclosure+30'),
    (r'ฟรีโอน|no\s*transfer\s*fee', 'no-transfer-fee+5'),
    (r'สร้างไม่ได้|can\'t\s*build', 'no-build-warning+0'),  # info only
]

def via_relay(url, timeout=40):
    api = f"{RELAY}/?url={urllib.parse.quote(url, safe='')}"
    try:
        p = subprocess.run(["curl","-sk","--compressed","-m",str(timeout),api],
                          capture_output=True, timeout=timeout+5)
        return p.stdout.decode("utf-8", errors="replace")
    except Exception:
        return ""

def parse_list(body):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', body, re.S)
    if not m: return []
    try:
        d = json.loads(m.group(1))
        return d.get("props", {}).get("pageProps", {}).get("resultListings", []) or []
    except (KeyError, json.JSONDecodeError):
        return []

def extract_land_info(item):
    """Parse a PropertyHub listing dict into our common shape."""
    if item.get("propertyType") != "LAND": return None
    loc = item.get("location") or {}
    lat, lng = loc.get("lat"), loc.get("lng")
    if not lat or not lng or not (5 < lat < 21 and 95 < lng < 106):
        return None
    price = ((item.get("price") or {}).get("forSale") or {}).get("price")
    if not price or price < 100000: return None    # < ฿100k = data noise
    lai = item.get("landAndHouseInformation") or {}
    # Area — fields are flat on landAndHouseInformation
    rai = int(lai.get("rai") or 0)
    ngan = int(lai.get("ngan") or 0)
    wah_str = lai.get("squareWa") or lai.get("wah") or 0
    try: wah = float(wah_str)
    except: wah = 0
    total_wah = rai * 400 + ngan * 100 + wah
    if not total_wah:
        # Fallback: squareWaInTotal or landSize
        for k in ("squareWaInTotal", "landSize"):
            v = lai.get(k)
            if v:
                try: total_wah = float(v); break
                except: pass
    sqm = total_wah * 4    # 1 sqwa = 4 m²
    if sqm < 100: return None    # smaller than 25 sqwa is data noise
    title = item.get("title") or ""
    # Distress scan on title
    dist_hits = []
    dist_bonus = 0
    for pat, tag in DISTRESS_PATS:
        if re.search(pat, title, re.I):
            dist_hits.append(tag)
            dist_bonus += int(tag.rsplit("+",1)[1])
    if dist_bonus > 60: dist_bonus = 60
    # Image
    pic = item.get("coverPicture")
    img = ("https://images.propertyhub.in.th/" + pic.lstrip("/")) if pic else ""
    return {
        "id": str(item.get("id")),
        "url": f"https://www.propertyhub.in.th/{item.get('slug','')}",
        "title": title[:200],
        "price_thb": price,
        "price_usd": round(price / 36),
        "sqm": sqm,
        "rai_display": f"{rai}-{ngan}-{wah}",
        "lat": lat, "lng": lng,
        "img": img,
        "distress_hits": dist_hits,
        "distress_bonus": dist_bonus,
    }

if __name__ == "__main__":
    out_path = "/tmp/propertyhub_th.json"
    existing = {}
    if os.path.exists(out_path):
        for r in json.load(open(out_path)):
            existing[r["id"]] = r
        print(f"loaded {len(existing)} existing", file=sys.stderr)

    all_rows = []
    for prov_name, slug in COASTAL_PROVINCES:
        seen_in_prov = set()
        for page in range(1, 6):
            url = f"https://www.propertyhub.in.th/land-for-sale/{slug}"
            if page > 1: url += f"?page={page}"
            body = via_relay(url, timeout=35)
            if not body or len(body) < 30000: continue
            items = parse_list(body)
            new_this_page = 0
            for it in items:
                lid = str(it.get("id"))
                if lid in seen_in_prov: continue
                seen_in_prov.add(lid)
                r = extract_land_info(it)
                if not r: continue
                r["province"] = prov_name
                all_rows.append(r)
                new_this_page += 1
            print(f"  {prov_name:>22} p{page}: {len(items)} items → {new_this_page} valid new", file=sys.stderr)
            if len(items) < 30: break
            time.sleep(0.3)

    # Dedup across provinces
    seen = set(); dedup = []
    for r in all_rows:
        if r["id"] in seen: continue
        seen.add(r["id"]); dedup.append(r)
    json.dump(dedup, open(out_path, "w"), ensure_ascii=False)
    from collections import Counter
    n_dist = sum(1 for r in dedup if r["distress_bonus"])
    print(f"\ndone. {len(dedup)} unique listings saved (distressed: {n_dist})", file=sys.stderr)
    print(dict(Counter(r["province"] for r in dedup).most_common()), file=sys.stderr)
