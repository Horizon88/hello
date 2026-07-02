# plantpeers autonomous loop
started_utc: 2026-07-02T09:10:22Z (1782983422)
deadline_utc: 2026-07-03T09:10:22Z (1783069822)
cadence: run a real round, commit+push, then schedule next wakeup; stop at deadline or when out of high-value work.

## Roadmap (reorder as signal dictates)
- [ ] L3  Trust/anti-gaming: verified outcomes vs self-reported stats (THE ballgame for TC)
- [ ] L4  Sweeper: real plant/cup photos (kill the dark placeholders) + card polish
- [ ] L5  Grower: instrument award-not-cheapest rate; buyer onboarding/skill capture
- [ ] L6  Maintainer: data-integrity guards + reliability of the (future) live-offer feed
- [ ] L7  Prototyper: seller/lab-side flow (submit an offer to an open request)
- [ ] L8  Discovery: search/browse depth, "watch this variety", request feed
- [ ] Lx  Completeness critic round: what's missing / weakest link

## Log
- L3 verified-outcome trust: SHIPPED (3d95284). Outcome ledger + beta-shrinkage; gamer lab caught (89->67, to last), honest labs hold, unverified pulled to prior. Prototyper+Builder.
- L4 Sweeper de-cruft + placeholders: SHIPPED (90faadb). Removed write-only persist() + dead fields; redesigned placeholders; caught+fixed SVG data-URI encoding bug (raw parens/quotes truncated url()) via shared svgURI(). Placeholders now paint.
- L5 Grower instrumentation: SHIPPED (3a82f37). award_metrics_v1 tally (survival-over-price / verified-lab / followed-rec / override gap / skill); catalog footer. Observe-only. Verified one-award writes + rates move.
- L6 Maintainer integrity: SHIPPED (470d834). scripts/validate_data.py (refs, ledger sanity, golden anti-gaming ranking) PASSes real data / fails bad edits; catalog graceful-degradation empty-state. Verified teeth.
