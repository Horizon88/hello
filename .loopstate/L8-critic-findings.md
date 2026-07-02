# L8 completeness-critic findings (ranked)

Adversarial audit of plantpeers after L1-L7. Source of the L9+ work list.

1. **Ledger is fabricated static JSON — no mechanism produces it.** The whole
   differentiator rests on 4 seeded numbers per lab; no identity/escrow/check-in/
   claim events exist. This is the "outcome spine" arc (big, needs product policy).
2. **[FIX L9] No-ledger/churned lab bypasses shrinkage — claim used at FACE VALUE.**
   enrich() no-ledger branch sets contam=claim raw. Gamer re-registers, claims 2%,
   escapes. Fix: pin no-ledger labs to prior (or worse); can't reach #1 without N
   witnessed outcomes.
3. **[FIX L9] Contamination proxy rewards DENYING claims.** contam=honored/shipments
   → deny claims = look cleaner. Fix: contamination from FILED claims; honor-rate a
   separate trust signal.
4. **Request inputs target/budget/deadline are decorative** — don't touch ranking.
   Fix: fold target into objective (P>=target / expected survivors), budget as soft
   penalty; or stop collecting. (Deferred — product decision.)
5. **[FIX L9] deflask_success ledger has NO effect for deflasked/acclimated.**
   survival() hardcodes 0.90/0.98. Fix: blend contam_deflask into per-plant term at
   all stages.
6. **[FIX L9] priceScore uncapped >100** — value exceeds its 20% budget; bar (capped)
   diverges from score (uncapped). Fix: clamp [0,100] in score().
7. **Buyer/lab ranking diverges** (late-offer holdback + live skill toggle). Fix:
   frozen skill for lab projection / rank range; consistent late-offer handling.
8. **[FIX L9] "verified" badge shows at thin tier; thin card shows raw not shrunk.**
   Fix: reserve "verified" for verified tier; show the shrunk value the model uses.
9. **Model duplicated in validate_data.py, golden test narrow** (one plant/skill).
   Fix: shared module; golden cases for churn/beginner/pro/per-plant coverage.
10. **Post-award & lab dead-ends; metrics trapped; acclimated penalized by cup
    contamination.** Fix: award->notify-lab + my-orders; drop pClean for acclimated;
    export metrics.

## Single biggest thing between this and real
The ledger no part of the system produces (#1). Until outcomes are witnessed and
written, the differentiator is a narrative. Recommended big arc: the "outcome spine"
(identity + escrow-gated 8-week check-in + claim filing) — needs product/PM policy.

## L9 scope (tractable now, no backend): #2,#3,#5,#6,#8 + acclimated pClean (#10 nit)
+ extend validate_data.py golden cases for the churn path. Makes the anti-gaming
thesis actually hold. Owner: Builder/Maintainer.
