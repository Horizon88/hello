# plantpeers

A peer-to-peer **tissue-culture plant marketplace**. Buyers browse a static
catalog of TC varieties, post what they want, and **labs compete to win the sale
on the odds the plant actually lives — not on price.**

This is a clickable, backend-free MVP (a single-file static web app with mock
data) built to prove the mechanic. See `CONTEXT.md` for the product brief and the
standing constraints.

## Why it's different from eBay

eBay is seller-listing-first: sellers post items, buyers hunt across near-
duplicate listings and do the comparison work. plantpeers inverts it:

1. **The catalog is canonical.** One entry per plant *type*, not thousands of
   listings.
2. **Demand comes first.** A buyer posts a Request (what plant, how many living
   plants they want, budget, deadline, their skill level).
3. **Labs compete for that sale.** Labs submit Offers; the buyer picks the best
   overall — judged on the *survival forecast*, not the sticker price.

Tissue culture makes this sharp: it's a high-trust, high-risk purchase
(contamination, failed deflasking, unstable variegation), so "which offer is most
likely to become a living plant" is exactly the right question.

## The model (`model.js` — one shared source of truth)

Every offer is ranked by a survival-weighted score, consumed identically by the
buyer compare view, the lab-side projected rank, and the data validator:

```
score = base * budgetFactor
base  = 0.45 * survivalComponent   (survival odds, scaled by fit to the buyer's target count)
      + 0.35 * labTrust            (verified contamination + deflask + honor-rate + rating)
      + 0.20 * priceScore          (cost per surviving plant, clamped 0..100)
```

- **survival()** — per-plantlet survival gated by stage (in-vitro / deflasked /
  acclimated), cup contamination softened by a replacement guarantee, and the
  buyer's own skill; yields odds-it-lives, expected live plants, and $/survivor.
- **labTrust()** — dominated by the lab's *ledger-derived* contamination and
  deflask-success rates (Beta-shrunk toward a cautious prior), plus a separate
  honor-rate signal so denying claims hurts.
- **Anti-gaming (the load-bearing part):** the two decisive numbers come from a
  witnessed outcome ledger, not lab self-report. New/no-ledger labs are pinned to
  the prior and can't hold #1 on an unproven claim; a churned account gains
  nothing; contamination is derived from *filed* claims so denying claims doesn't
  hide it. `experiments/verified_trust_spike.html` and
  `experiments/outcome_spine_spike.html` explore how the ledger gets minted.

## Architecture

```
plantpeers/
  index.html            the app (inline CSS/JS; loads model.js + fetches data/*.json)
  model.js              shared scoring model (window.PPModel + module.exports)
  data/
    plants.json         static catalog (TC varieties)
    sellers.json        labs: reputation + witnessed outcome ledger
    offers.json         competing offers (stage, plantlets, price, specs)
    reviews.json        TC-outcome reviews
    requests.json       seed open buyer requests
  scripts/
    validate_data.py    data-integrity + golden-ranking + anti-gaming checks (CI guard)
    build_standalone.py bundles everything into one self-contained file
  dist/
    plantpeers.standalone.html   single-file build (runs with no server)
    plantpeers.artifact.html     body-only fragment for hosted publishing
  experiments/          throwaway spikes (the ideas behind each feature)
  CONTEXT.md            product brief + constraints
```

## Run it

Multi-file (canonical), from `plantpeers/`:

```bash
python3 -m http.server 8000
# open http://localhost:8000/index.html  (mobile-first: ~390px wide)
```

Single self-contained file (no server needed — data + model inlined):

```bash
python3 scripts/build_standalone.py
# open dist/plantpeers.standalone.html directly
```

## The flow

- **Buyer:** browse → tap a plant → set quantity/budget/skill → post request →
  offers rank by survival odds (a late offer arrives and re-ranks) → compare with
  the "BEST ODDS" hero, value meter, and trade-off ribbons → award → it lands in
  **📦 My orders**.
- **Lab:** "I'm a lab" → pick your lab → open a request → the offer builder shows
  your **locked verified ledger** (you can't type those numbers), a **live
  projected rank**, and a coach: dropping price barely moves rank, adding a
  replacement guarantee jumps it. Submit → the buyer's compare updates → you see
  **✓ Won** when they award you.

## Test / verify

```bash
python3 scripts/validate_data.py     # referential integrity, ledger sanity,
                                     # golden ranking (gamer ranks last), anti-gaming
```

The golden-ranking check runs the real `model.js` via node (skips gracefully if
node is absent). It's the intended pre-commit / CI guard for any data or model
change.

## Quality bars already met

- **Accessibility:** keyboard-operable, focus-visible rings, ARIA labels,
  `prefers-reduced-motion`, AA contrast.
- **Security:** user-controlled fields are escaped; ids use data-attribute event
  delegation (no id-into-onclick); `hero_img` scheme-allowlisted. XSS-regression
  tested.
- **No third-party CDN:** placeholder art is inline SVG; nothing breaks offline.

## The one big open thing

The trust ledger is still **seeded mock data** — no part of the system yet
*produces* it. Making it real is the "outcome spine": durable lab identity,
escrow-gated 8-week "did it live?" check-ins, and a frictionless claim flow that
mint the ledger from real events. `experiments/outcome_spine_spike.html`
demonstrates the mechanism and lays out the product-policy decisions it needs
(incentive strength, where the prior sits, claim adjudication). That's the next
real arc — and it needs a backend and founder input, not just more mock data.
