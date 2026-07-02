# plantpeers.com — project context

Grounding doc for the venture studio team. Any role working in `plantpeers/`
reads this first. (Convention: every project in this repo carries its own
`CONTEXT.md`.)

## What it is

A peer-to-peer plant marketplace. Buyers browse a **static catalog** of plant
*types* (species/variety/size class), express intent to buy one, and **sellers
compete to win that specific sale**.

## What makes it different from eBay

eBay is *seller-listing-first*: each seller posts their own item, buyers hunt
across near-duplicate listings, and the buyer does the comparison work. plantpeers
inverts this:

1. **The catalog is static and canonical.** There is one entry for
   "Monstera adansonii — medium, ~6in pot", not thousands of seller listings for
   it. Buyers shop clean plant *types*, not a feed of listings.
2. **Demand comes first.** A buyer signals "I want this plant" (a Request).
3. **Sellers compete for that sale.** Sellers who can fulfill it submit Offers.

## The competition mechanic (decided)

**Quality + reputation match — the buyer picks the best offer, not the cheapest.**

When a Request is open, each competing seller submits an Offer containing:
- actual **photos** of the specific plant they'd ship (not catalog stock art),
- **specs**: current size/height, leaf/node count, pot size, health notes,
  age, whether it's the exact phenotype, ships-with-pot, etc.,
- **price** and shipping/ETA,
- their **reputation** (rating, sales count, buyer reviews, verified badges,
  return/DOA policy).

The buyer compares offers side-by-side and **chooses the winner on overall value
— plant quality and seller trust — not lowest price alone.** Price is one input,
not the ranking. This is the core loop; everything serves making that comparison
fast, fair, and trustworthy.

## Data model (MVP)

| Entity | Key fields |
|---|---|
| **Plant** (catalog, static) | `id`, `common_name`, `latin_name`, `variety`, `size_class`, `care_level`, `light`, `hero_img`, `description` |
| **Seller** | `id`, `handle`, `avatar`, `rating` (0–5), `sales_count`, `reviews[]`, `badges[]` (e.g. verified, fast-shipper, DOA-guarantee), `location`, `response_time` |
| **Buyer** | `id`, `handle`, `location` |
| **Request** (buyer intent) | `id`, `plant_id`, `buyer_id`, `notes` (size wanted, budget hint, deadline), `status` (open/awarded/closed), `created` |
| **Offer** (seller competes) | `id`, `request_id`, `seller_id`, `photos[]`, `specs{height,leaves,pot,health,phenotype}`, `price`, `shipping`, `eta_days`, `message`, `submitted` |
| **Review** | `id`, `seller_id`, `buyer_id`, `stars`, `text`, `plant_id`, `date` |

## First-loop deliverable

A **clickable MVP prototype**: a static web app (served like the land scanner —
HTML/CSS/JS, mock data in JSON, no backend yet) that walks the full loop:

1. **Browse catalog** — grid of plant types with search/filter.
2. **Request a plant** — pick a plant, add notes (size/budget/deadline), open a
   Request.
3. **Sellers compete** — Offers appear against the Request (seeded mock offers,
   with a fake "new offer just arrived" beat to convey the compete dynamic).
4. **Compare & pick winner** — side-by-side offer comparison surfacing photos,
   specs, price, and reputation; buyer awards the sale to one seller.
5. **Confirmation** — the awarded offer, why-it-won summary.

Mock data lives in `plantpeers/data/*.json`; the app is `plantpeers/index.html`
(plus assets). Keep it runnable by `python -m http.server` from `plantpeers/`.

## Stack / conventions

- Static single-page app first (mirrors the proven pattern in this repo): plain
  HTML/CSS/vanilla JS, data loaded from JSON. No backend/build step for the MVP.
- No hard dependency on a third-party CDN that, if it fails, breaks the core
  flow (lesson from the land scanner's Leaflet incident — degrade gracefully).
- Keep it idempotent + reviewable: small commits, one concern each.

## Standing user preferences (hard constraints)

- **Mobile-first.** Design for a phone screen; the compare-offers view must work
  well on mobile.
- Prefers **proposals + immediate execution**, not multi-step confirmation loops.
- Do max work autonomously; only ask when it genuinely needs the user's account
  access (secrets, repo creation, OAuth) or a true product fork.
- In chat replies: no bold-link markdown; keep it concise.

## Open questions (park, don't block the MVP)

- Payments/escrow, dispute/DOA handling, and anti-sniping on offer windows are
  post-MVP. The MVP fakes fulfillment at "award."
- Whether Requests are public (any seller can bid) or routed only to sellers who
  stock that plant — MVP assumes public-to-qualified-sellers.
