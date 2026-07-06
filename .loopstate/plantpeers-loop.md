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
- L7 lab-side / two-sided marketplace: SHIPPED (df8edf5). Lab console + offer builder w/ locked verified ledger, live projected rank, coach (guarantee +3 ranks vs price cut 0). Shared model (no drift). Buyer ranking byte-identical. Prototyper+Builder.
- L8 = completeness-critic round (find weakest link) then act on top finding.
- L8 critic: ranked audit -> .loopstate/L8-critic-findings.md.
- L9 anti-gaming fixes: SHIPPED (89a3a91). #2 no-ledger pinned to prior + cant hold #1; #3 contamination from filed claims + honor-rate trust signal; #5 deflask ledger into survival; #6 priceScore clamp; #8 thin badge; #10 acclimated pClean. Validator churn-attack case PASS. Builder.
- L10 = #9 shared model module + #7 skill divergence (last tractable round). Then #1 outcome-spine + #4 request-inputs need user product input -> slow cadence.
- L10 shared model.js + skill-divergence fix: SHIPPED (b4347f7). One model.js consumed by app+validator (node), -133 lines index.html; lab projection frozen skill + late-offer consistency. Sweeper.
- L11 = #4 fold request target/budget into ranking objective (last clearly-valuable no-backend round). Then L12 = outcome-spine PROTOTYPE spike (explore #1 w/o committing product/backend), then HOLD (long wakeup) pending user product decision.
- L11 request-needs into ranking: SHIPPED (3392f02). target-fit multiplier on survival + soft budget penalty + over-budget/late flags; anti-gaming preserved; needs-move-ranking golden case. Grower.
- L12 = outcome-spine PROTOTYPE spike (explore #1: mint ledger from award->checkin->claim events, client-side sim). Then HOLD for user product decision.
- L12 outcome-spine spike: SHIPPED (1601706). experiments/outcome_spine_spike.html mints ledger from events; trust converges to hidden truth; participation sliders; anti-gaming (denier honor-rate hit, churn->prior). Frames founder decision. Prototyper.
- L13 = security review (XSS in innerHTML string-template rendering of user content).
- L13 security review + L13b fix: SHIPPED (ffd2fb5). Quote-aware esc(); id->data-attr delegation; hero_img scheme allowlist; numeric coercion. Exploit-blocked (control-tested); app intact, gamer last.

## MILESTONE (after L13b): comprehensive build complete. Transition to heartbeat cadence.
Remaining backlog (paced, lower priority — do 1 per wake if genuinely worth it, else hold):
- [x] audit #10: post-award my-orders + lab "Won" state — SHIPPED L14 (685d17f)
- [ ] accessibility pass (aria/labels/contrast/focus order on mobile)
- [ ] seed-data richness (more varieties/labs/offers for a fuller demo)
- [ ] plantpeers README + short landing/pitch page
- [ ] BLOCKED ON USER: #1 outcome spine (identity+escrow+checkin+claim) — needs product policy; L12 spike demonstrates the mechanism.
Stop heavy multi-agent rounds unless clearly high-value; re-verify + re-arm otherwise; stop at deadline 09:10Z or when backlog exhausted.
- L14 post-award my-orders + lab Won: SHIPPED (685d17f). localStorage orders, "My orders" view + reopen detail, lab "✓ Won" section. XSS-safe. Builder.
- Recovered from a container restart (17:06Z) — repo intact, toolchain ok. Heartbeat re-armed.
- Standalone build + Artifact: SHIPPED (02d7fb4). scripts/build_standalone.py inlines model.js+data -> dist/plantpeers.standalone.html + .artifact.html (works file://, no server). Published Artifact: https://claude.ai/code/artifact/5368d6c7-de43-4f79-90b7-70721f074088 (redeploy same file_path to update same URL).
- L15 = richer seed data (fuller catalog + more labs/offers) so the live demo feels complete, then REBUILD standalone + REDEPLOY artifact (same URL).
- L15 richer seed data: SHIPPED (c8865e6). 16 plants / 13 labs / 57 offers / 22 reviews / 3 requests; validator GREEN, FB golden + anti-gaming intact; standalone rebuilt (168KB). Builder.
- ARTIFACT REDEPLOY BLOCKED: same-URL redeploy of the richer build failed 3x ("permission stream closed") in non-interactive continuation. The live Artifact (5368d6c7...) still shows the OLD 8-plant data. TODO: redeploy dist/plantpeers.artifact.html to the same URL on the next INTERACTIVE turn. Updated standalone sent to user directly meanwhile.
