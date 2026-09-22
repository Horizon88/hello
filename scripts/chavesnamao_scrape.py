"""chavesnamao.com.br — Brazil coastal land scrape (targeted by region).

The big Brazil portals (vivareal/zap/OLX) are Cloudflare-walled, but
chavesnamao serves full SSR pages on a DIRECT fetch, and every listing URL
encodes the data:
  /imovel/terreno-a-venda-<uf>-<city>-<neighborhood>-<area>m2-RS<price>/id-<id>/
so area, price, location and id come straight from the slug (no detail
fetch). Paginates ?filtro=or:N. No coords, so geocode by neighborhood+city.

Targets the Santa Catarina coast (top foreigner beach market). Change CITIES
to retarget another region. Emits /tmp/chavesnamao.json for the merge.
"""
import json, os, re, subprocess, sys, time, urllib.parse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = "/tmp/chavesnamao.json"
GEO_CACHE = "/tmp/chavesnamao_geo.json"
MAX_PAGES = 25            # ~16/page

# Santa Catarina coast — the targeted region (chavesnamao city slugs)
CITIES = [
    ("sc", "florianopolis"), ("sc", "balneario-camboriu"), ("sc", "bombinhas"),
    ("sc", "garopaba"), ("sc", "itapema"), ("sc", "porto-belo"),
    ("sc", "governador-celso-ramos"), ("sc", "imbituba"), ("sc", "penha"),
    ("sc", "itajai"), ("sc", "navegantes"), ("sc", "tijucas"),
]

def curl(url, timeout=30):
    try:
        return subprocess.run(["curl", "-sk", "-m", str(timeout), "-A", UA, url],
                              capture_output=True, text=True, timeout=timeout + 5).stdout
    except Exception:
        return ""

SLUG = re.compile(
    r'/imovel/terreno-a-venda-([a-z]{2})-([a-z0-9\-]+?)-([\d.]+)(m2|ha|hectares?)-RS([\d.]+)/id-(\d+)/')

def parse_page(html, uf, city):
    out = []
    for l in set(re.findall(r'/imovel/terreno-a-venda[^"\s\\]+/id-\d+/', html)):
        m = SLUG.search(l)
        if not m:
            continue
        u, loc, area, unit, price, lid = m.groups()
        if u != uf:
            continue
        # loc starts with the city slug; the remainder is the neighborhood
        nb = loc[len(city):].strip("-") if loc.startswith(city) else loc
        try:
            sqm = float(area.replace(".", "")) * (10000 if unit.startswith("h") else 1)
            rm = int(price.replace(".", ""))
        except Exception:
            continue
        if sqm < 40 or rm < 5000:
            continue
        out.append({
            "id": lid,
            "url": "https://www.chavesnamao.com.br" + l.rstrip("\\"),
            "uf": u.upper(), "city": city.replace("-", " ").title(),
            "neighborhood": nb.replace("-", " ").title(),
            "sqm": round(sqm, 1), "price_rm": rm,
        })
    return out

STATE_CENTROID = {"SC": (-27.3, -48.6)}
def geocode(nb, city, uf, cache):
    key = f"{nb}|{city}|{uf}"
    if key in cache:
        return cache[key]
    for q in (f"{nb}, {city}, {uf}, Brazil", f"{city}, {uf}, Brazil"):
        body = curl("https://nominatim.openstreetmap.org/search?format=json&limit=1&q=" +
                    urllib.parse.quote(q), timeout=20)
        time.sleep(1.1)
        try:
            j = json.loads(body)
        except Exception:
            j = []
        if j:
            cache[key] = [round(float(j[0]["lat"]), 5), round(float(j[0]["lon"]), 5), "osm"]
            json.dump(cache, open(GEO_CACHE, "w")); return cache[key]
    la, lo = STATE_CENTROID.get(uf, (-27.3, -48.6))
    cache[key] = [la, lo, "state"]; json.dump(cache, open(GEO_CACHE, "w")); return cache[key]

def main():
    out = {}
    if os.path.exists(OUT):
        for r in json.load(open(OUT)):
            out[r["id"]] = r
    cache = json.load(open(GEO_CACHE)) if os.path.exists(GEO_CACHE) else {}

    for uf, city in CITIES:
        got = 0
        for pg in range(0, MAX_PAGES):
            url = f"https://www.chavesnamao.com.br/terrenos-a-venda/{uf}-{city}/" + (f"?filtro=or:{pg}" if pg else "")
            recs = parse_page(curl(url), uf, city)
            if not recs:
                break
            new = 0
            for r in recs:
                if r["id"] not in out:
                    out[r["id"]] = r; new += 1; got += 1
            if new == 0:
                break
            time.sleep(0.3)
        print(f"  {uf}-{city}: +{got} (total {len(out)})", file=sys.stderr)
        json.dump(list(out.values()), open(OUT, "w"))

    uniq = {(r["neighborhood"], r["city"], r["uf"]) for r in out.values()}
    print(f"geocoding {len(uniq)} localities…", file=sys.stderr)
    for nb, city, uf in uniq:
        geocode(nb, city, uf, cache)
    for r in out.values():
        g = cache.get(f"{r['neighborhood']}|{r['city']}|{r['uf']}")
        if g:
            r["lat"], r["lng"], r["geo_src"] = g[0], g[1], g[2]

    json.dump(list(out.values()), open(OUT, "w"))
    coded = sum(1 for r in out.values() if r.get("lat"))
    print(f"TOTAL {len(out)} chavesnamao land rows ({coded} geocoded) -> {OUT}", file=sys.stderr)

if __name__ == "__main__":
    main()
