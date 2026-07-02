# L13 security review findings

model.js clean (pure fns). Free-text is correctly escaped via esc() in TEXT
context (review text, notes, names) — `<img onerror>` does NOT fire there.
The hole: esc() is QUOTE-BLIND and data values land in attribute/handler contexts.

esc() currently: `String(s).replace(/&/,'&amp;').replace(/</,'&lt;').replace(/>/,'&gt;')`
— missing " and '.

1. HIGH — ids interpolated into onclick="fn('...')":
   - NO escape: renderCatalog openPlant('+p.id+') (~736); card award('+o.id+') (~984);
     renderLabPicker enterLab('+s.id+') (~1203).
   - esc'd but quotes pass: renderLabRequests openLabOffer(esc(r.id)) (~1232);
     showLabSubmitted viewRequestAsBuyer(esc(LAB.request.id)) (~1527);
     renderFilters setFilter(esc(l)) (~708, l=care_level).
   Exploit: a JSON id like `><img src=x onerror=...>` fires on render (no-escape ones);
   esc'd ones allow `" onmouseover=...` handler injection.
   FIX: prefer addEventListener + data-id (read el.dataset.id); at minimum make esc()
   quote-aware AND wrap the raw p.id/o.id/s.id.

2. HIGH — p.hero_img raw into style='background-image:url(...)' (renderCatalog ~737,
   openPlant ~754). Exploit: hero_img=`x'></div><img src=x onerror=...>` fires on render.
   FIX: restrict scheme (^(https?:|data:image/)) + quote-encode; leafSVG/cupSVG/avSVG are
   already safe via svgURI().

3. MED — assumed-numeric fields raw in text context: o.rating/o.sales (~974),
   s.rating/s.sales_count (~1206/1286), o.shipments (~1207), o.eta_days (~962/888).
   FIX: Number() coerce or esc().

4. LOW — search echo esc(q) (~733): self-only, tags blocked. Acceptable.

localStorage: handled well (try/catch, sellerId validated vs sellerById, no string
from LS reaches innerHTML). No finding. No target=_blank/noopener gap.

## Fix plan (L13b, Builder): make esc() quote-aware (" -> &quot;, ' -> &#39;);
convert id->onclick to addEventListener+data-id (or wrap raw ids in esc); validate+
escape hero_img scheme; coerce numerics. Verify with exploit payloads in a data copy
(no execution). Keep validator PASS + gamer-last.
