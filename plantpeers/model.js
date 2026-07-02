/* ============================================================
   PlantPeers SURVIVAL / TRUST / RANK MODEL — THE single source of truth.

   This one file holds the entire scoring model (priors, weights, betaMean,
   confidenceTier, enrich, survival, labTrust, score, recompute and the
   anti-gaming #1-slot rule). It is consumed unchanged in TWO places:

     * the browser — index.html loads it via <script src="model.js"> BEFORE its
       inline script and reads window.PPModel (no build step).
     * Node       — scripts/validate_data.py shells out to `node` which
       require()s this file, so the validator's golden ranking is computed by
       the SAME code the app runs. There is no re-implementation to drift from.

   Everything is a pure function of its inputs (offer + seller + buyer skill);
   nothing here touches the DOM, fetch, or globals other than the export object.
   ============================================================ */
(function (global) {
  "use strict";

  /* buyer TC experience -> per-plantlet deflask multiplier */
  var SKILL = { beg: 0.65, some: 0.85, pro: 1.0 };

  /* ---- BUYER-NEEDS knobs (target quantity / budget / deadline) ----
     The request form collects how many LIVING plants the buyer wants (target),
     a max shipped $ (budget) and a by-when (deadline). These shape the ranking:
       * TARGET_W  — the share of the survival credit that is governed by hitting
         the desired count (the rest is the plain "at least one lives" odds). It
         REFINES survival; it is never a fresh pool of points a low-trust lab can
         farm by stuffing plantlets — see score()/the anti-gaming note.
       * BUDGET_SLOPE / BUDGET_FLOOR — an over-budget offer is SOFT-penalised
         (multiplicative), never hard-filtered: it keeps at least BUDGET_FLOOR of
         its score so a great over-budget option is still visible, just can't win
         over a comparable in-budget one.
     Deadline is display-only (an eta-vs-by-when flag); it does not move score. */
  var TARGET_W = 0.25;
  var BUDGET_SLOPE = 0.5;
  var BUDGET_FLOOR = 0.6;

  /* Beta-shrinkage priors: assume ~10% contamination / ~65% establishment until a
     lab's witnessed ledger proves otherwise. Strength = pseudo-count of evidence. */
  var CONTAM_PRIOR = 0.10, CONTAM_STRENGTH = 25;
  var DEFLASK_PRIOR = 0.65, DEFLASK_STRENGTH = 20;

  /* Beta posterior mean shrunk toward the platform prior. Few outcomes -> stays
     near the prior (an unproven optimistic claim is discounted); many outcomes ->
     the ledger dominates and the claim is ignored. */
  function betaMean(k, n, priorRate, strength) {
    var a0 = priorRate * strength, b0 = (1 - priorRate) * strength;
    return (a0 + k) / (a0 + b0 + n);
  }

  /* Parse the buyer's free-text request notes into the NUMERIC needs the ranking
     reads: desired living-plant count (target), max shipped $ (budget), and a
     by-when eta in days (deadline). An absent / unparseable field returns null ==
     "no constraint", so a request missing a field ranks EXACTLY as it did before
     this feature existed (graceful default). Consumed by recompute()/score(). */
  function parseTarget(str) {
    if (str == null) return null;
    var t = String(str).toLowerCase();
    if (/as many|as possible|maximum|max out/.test(t)) return 8; // "more is better"
    var m = t.match(/\d+/);
    return m ? parseInt(m[0], 10) : null;                        // first number: "4+"->4, "2-3"->2
  }
  function parseBudget(str) {
    if (str == null) return null;
    var t = String(str).toLowerCase();
    if (/regardless|any price|best odds/.test(t)) return null;   // explicit "price is no object"
    var m = t.match(/\d+/);
    return m ? parseInt(m[0], 10) : null;
  }
  function parseDeadline(str) {
    if (str == null) return null;
    var t = String(str).toLowerCase();
    if (/no rush|whenever|flexible/.test(t)) return null;
    if (/asap|urgent/.test(t)) return 3;
    var wk = t.match(/(\d+)\s*week/);
    if (wk) return parseInt(wk[1], 10) * 7;
    if (/next week|this week|a week|1 week|one week/.test(t)) return 7;
    var dm = t.match(/(\d+)\s*day/);
    if (dm) return parseInt(dm[1], 10);
    return null;
  }
  function parseNeeds(notes) {
    notes = notes || {};
    return {
      target: parseTarget(notes.target),
      budget: parseBudget(notes.budget),
      deadline: parseDeadline(notes.deadline)
    };
  }

  /* Is a lab's ledger deep enough to trust over its claim? */
  function confidenceTier(shipments, checkins) {
    if (shipments >= 60 && checkins >= 40) return "verified";
    if (shipments >= 20) return "thin";
    return "unverified";
  }

  /* Fold a raw offer + its seller into the model object the ranking reads. The two
     decisive inputs (contam, contam_deflask) come ONLY from the witnessed ledger,
     Beta-shrunk to the prior — never the lab's self-report. A no/thin ledger is
     pinned to the cautious prior so dropping the ledger and claiming 0%/100% buys
     nothing. Also carries the ledger-display fields the buyer/lab UI surfaces. */
  function enrich(offer, seller) {
    offer = offer || {};
    seller = seller || {};
    var o = {};
    o.id = offer.id;
    o.plant_id = offer.plant_id;
    o.seller_id = offer.seller_id;
    o.handle = seller.handle || ("@" + offer.seller_id);
    o.rating = seller.rating || 0;
    o.sales = seller.sales_count || 0;
    o.certsCount = seller.certs ? seller.certs.length : 0;
    o.contamClaimed = (seller.contamination_rate_claimed != null) ? seller.contamination_rate_claimed : 0.15;
    o.deflaskClaimed = (seller.deflask_success_rate_claimed != null) ? seller.deflask_success_rate_claimed : 0.6;

    var lg = seller.ledger;
    if (lg && lg.shipments > 0 && lg.checkins_responded > 0) {
      o.hasLedger = true;
      o.shipments = lg.shipments;
      o.checkins = lg.checkins_responded;
      // witnessed contamination = FILED claims / shipments (denying claims can't hide it)
      var filed = (lg.filed_claims != null) ? lg.filed_claims : lg.honored_claims;
      o.filedClaims = filed;
      o.honoredClaims = lg.honored_claims;
      o.contamVerified = filed / lg.shipments;
      o.deflaskVerified = lg.establishment_confirmed / lg.checkins_responded;
      // honor rate is a SEPARATE trust signal (denying filed claims hurts it)
      o.honorRate = filed > 0 ? lg.honored_claims / filed : 1;
      o.confidence = confidenceTier(lg.shipments, lg.checkins_responded);
      o.contam = betaMean(filed, lg.shipments, CONTAM_PRIOR, CONTAM_STRENGTH);
      o.contam_deflask = betaMean(lg.establishment_confirmed, lg.checkins_responded, DEFLASK_PRIOR, DEFLASK_STRENGTH);
      if (o.confidence === "unverified") {
        // ledger too thin to believe: never better than the cautious prior
        o.contam = Math.max(CONTAM_PRIOR, o.contam);
        o.contam_deflask = Math.min(DEFLASK_PRIOR, o.contam_deflask);
      }
    } else {
      // no ledger (churned / re-registered lab): pin to the prior, distrust the claim
      o.hasLedger = false;
      o.confidence = "unverified";
      o.contam = Math.max(CONTAM_PRIOR, o.contamClaimed);
      o.contam_deflask = Math.min(DEFLASK_PRIOR, o.deflaskClaimed);
      o.contamVerified = null;
      o.deflaskVerified = null;
      o.honorRate = null;
      o.filedClaims = 0;
      o.honoredClaims = 0;
    }

    // Replacement guarantee: an explicit per-offer override (from the lab console
    // toggle) wins; otherwise fall back to the seller's standing policy.
    var rp = seller.replacement_policy || {};
    o.replace = (offer.replacement_override != null) ? !!offer.replacement_override : !!rp.covers;

    o.stage = offer.stage;
    o.plantlets = offer.plantlets_per_cup || 1;
    o.price = offer.price || 0;
    o.shipping = offer.shipping || 0;
    o.eta = (offer.eta_days != null) ? offer.eta_days : null; // for the deadline flag (display-only)
    return o;
  }

  /* Odds the buyer ends up with a living plant, given stage, ledger-derived
     establishment/contamination, plantlet count, replacement policy and skill. */
  function survival(o, skill) {
    var sk = SKILL[skill];
    var perPlant;
    if (o.stage === "invitro") perPlant = o.contam_deflask * sk;      // buyer deflasks; skill matters
    else if (o.stage === "deflasked") perPlant = 0.80 + 0.18 * o.contam_deflask; // lab establishment shows through
    else perPlant = 0.90 + 0.09 * o.contam_deflask;                   // acclimated: ledger nudges
    var effContam = o.replace ? o.contam * 0.15 : o.contam;
    var pClean = (o.stage === "acclimated") ? 1 : (1 - effContam);    // acclimated: cup risk retired
    var n = o.plantlets;
    var pAtLeastOne = pClean * (1 - Math.pow(1 - perPlant, n));
    var expLive = pClean * n * perPlant;
    var total = o.price + o.shipping;
    var costPerLive = expLive > 0 ? total / expLive : 999;
    return {
      perPlant: perPlant, pClean: pClean, pAtLeastOne: pAtLeastOne, expLive: expLive,
      costPerLive: costPerLive, total: total, moneyAtRisk: o.replace ? 0 : total
    };
  }

  /* Lab-trust score (0-100). Contamination + deflask track record dominate;
     replacement guarantee, certs, rating, volume and honor-rate fold in. */
  function labTrust(o) {
    var contamScore = Math.max(0, 1 - o.contam / 0.25);
    var deflaskScore = o.contam_deflask;
    var ratingScore = (o.rating || 0) / 5;
    var volScore = Math.min(1, Math.log10((o.sales || 0) + 1) / Math.log10(500));
    var certScore = Math.min(1, (o.certsCount || 0) / 2);
    var honorScore = (o.honorRate != null) ? o.honorRate : 0.85;
    var raw = 0.30 * contamScore + 0.18 * deflaskScore + 0.12 * ratingScore
      + 0.08 * volScore + 0.10 * certScore + 0.10 * (o.replace ? 1 : 0) + 0.12 * honorScore;
    return Math.round(raw * 100);
  }

  /* TARGET fit: how well an offer's EXPECTED SURVIVORS meet the buyer's desired
     living-plant count. 1 == meets/exceeds the target; <1 falls short. Absent
     target -> 1 (no effect). This is the lever that lets a 6-plantlet cup (whose
     expected live count clears "a few (4+)") out-rank a single acclimated plant. */
  function targetFit(expLive, needs) {
    if (!needs || needs.target == null || needs.target <= 0) return 1;
    return Math.min(1, expLive / needs.target);
  }

  /* BUDGET soft penalty: an over-budget offer is DOWN-WEIGHTED in proportion to how
     far over it is, but never below BUDGET_FLOOR of its score and never hidden — a
     great over-budget option still appears, it just can't win over a comparable
     in-budget one. In-budget (or no budget stated) -> 1 (untouched). */
  function budgetPenalty(o, needs) {
    if (!needs || needs.budget == null || needs.budget <= 0) return 1;
    var total = o.price + o.shipping;
    if (total <= needs.budget) return 1;
    var over = total / needs.budget - 1;              // 0.5 == 50% over budget
    return Math.max(BUDGET_FLOOR, 1 - over * BUDGET_SLOPE);
  }

  /* Composite RANK score: survival(0.45) + lab-trust(0.35) + value(0.20), then the
     buyer's stated needs shape it: the survival credit is refined by TARGET fit
     (do the expected survivors meet the desired count?), and the whole score is
     scaled by the soft BUDGET penalty. Value is cost-per-expected-live-plant,
     clamped [0,100] so a cheap-but-doomed cup can't win.

     ANTI-GAMING: target enters as a MULTIPLIER on the survival credit (bounded by
     [1-TARGET_W, 1]), not as a new additive pool of points. A low-trust lab that
     stuffs plantlets still earns survival credit only in proportion to its (low)
     per-plant survival, and lab-trust(0.35) is untouched — so hitting the count
     cannot buy a churned/untrusted lab up the board. */
  function score(o, skill, needs) {
    var s = survival(o, skill);
    var survScore = s.pAtLeastOne * 100;
    var priceScore = Math.max(0, Math.min(100, 100 - (s.costPerLive - 15) * 1.5));
    var tf = targetFit(s.expLive, needs);
    var survComponent = survScore * (1 - TARGET_W + TARGET_W * tf);
    var base = 0.45 * survComponent + 0.35 * labTrust(o) + 0.20 * priceScore;
    return base * budgetPenalty(o, needs);
  }

  /* Stamp the display-only needs flags the buyer UI reads onto the offer: is it
     over budget (and by how much), does its expected live count meet the target,
     and does its eta miss the by-when deadline. Pure annotation — the ranking is
     already decided by score(); deadline in particular NEVER moves score. */
  function annotateNeeds(o, needs) {
    needs = needs || {};
    var s = o._s || survival(o, "some");
    var total = o.price + o.shipping;
    o._overBudget = (needs.budget != null && total > needs.budget);
    o._overBudgetBy = o._overBudget ? total - needs.budget : 0;
    o._targetFit = (needs.target != null && needs.target > 0) ? targetFit(s.expLive, needs) : null;
    o._target = (needs.target != null) ? needs.target : null;
    o._meetsTarget = (o._target != null) ? (s.expLive >= o._target - 1e-9) : null;
    o._lateEta = (needs.deadline != null && o.eta != null) ? (o.eta > needs.deadline) : false;
    o._etaGap = o._lateEta ? o.eta - needs.deadline : 0;
    o._deadline = (needs.deadline != null) ? needs.deadline : null;
  }

  /* An offer may hold #1 only if it has witnessed outcomes (tier != unverified). */
  function rankEligibleForTop(o) { return o.confidence !== "unverified"; }

  /* Anti-gaming hard rule: a no/thin-ledger (unverified) offer cannot rank first
     while any ledger-backed offer exists — stops the churn attack. arr is already
     score-sorted, so the first eligible offer found is the best-scoring one. */
  function enforceVerifiedFirst(arr) {
    if (arr.length < 2 || rankEligibleForTop(arr[0])) return;
    for (var i = 1; i < arr.length; i++) {
      if (rankEligibleForTop(arr[i])) { arr.unshift(arr.splice(i, 1)[0]); return; }
    }
  }

  /* Recompute survival/trust/score for `skill` and the buyer's `needs` (target/
     budget/deadline — pass numeric needs, e.g. from parseNeeds(); omitted == no
     constraints == behaves exactly as before this feature), sort by score desc,
     apply the #1-slot rule. Sets o._s / o._lt / o._score and the needs flags in
     place (the UI reads o._s and o._overBudget/_targetFit/_lateEta). */
  function recompute(arr, skill, needs) {
    needs = needs || {};
    arr.forEach(function (o) { o._s = survival(o, skill); o._lt = labTrust(o); });
    arr.forEach(function (o) { o._score = score(o, skill, needs); annotateNeeds(o, needs); });
    arr.sort(function (a, b) { return b._score - a._score; });
    enforceVerifiedFirst(arr);
    return arr;
  }

  var PPModel = {
    SKILL: SKILL,
    CONTAM_PRIOR: CONTAM_PRIOR, CONTAM_STRENGTH: CONTAM_STRENGTH,
    DEFLASK_PRIOR: DEFLASK_PRIOR, DEFLASK_STRENGTH: DEFLASK_STRENGTH,
    TARGET_W: TARGET_W, BUDGET_SLOPE: BUDGET_SLOPE, BUDGET_FLOOR: BUDGET_FLOOR,
    betaMean: betaMean,
    parseTarget: parseTarget, parseBudget: parseBudget, parseDeadline: parseDeadline,
    parseNeeds: parseNeeds,
    confidenceTier: confidenceTier,
    enrich: enrich,
    survival: survival,
    labTrust: labTrust,
    targetFit: targetFit,
    budgetPenalty: budgetPenalty,
    annotateNeeds: annotateNeeds,
    score: score,
    rankEligibleForTop: rankEligibleForTop,
    enforceVerifiedFirst: enforceVerifiedFirst,
    recompute: recompute
  };

  global.PPModel = PPModel;
  if (typeof module !== "undefined" && module.exports) { module.exports = PPModel; }
})(typeof window !== "undefined" ? window : (typeof globalThis !== "undefined" ? globalThis : this));
