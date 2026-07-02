#!/usr/bin/env python3
"""
plantpeers data-integrity validator  (L6, reliability-only)

The plantpeers MVP is a static app whose ENTIRE ranking depends on the shape and
internal consistency of the mock data in ../data/*.json. A bad data edit today
fails silently in the browser (blank cards, wrong winner) rather than loudly.
This script is the cheap guard that catches such a regression BEFORE it ships.

Run:   python3 plantpeers/scripts/validate_data.py
Exit:  0 = all invariants hold (prints a PASS summary with counts)
       1 = at least one invariant violated (prints clear FAIL messages)

Pure standard library. No dependencies. Safe to run in CI / pre-commit.

What it asserts (the invariants index.html relies on):
  * Referential integrity — every offer.seller_id / offer.plant_id, every
    review.seller_id / review.plant_id, and the seed request.plant_id resolve.
  * Required fields present with sane types/ranges (plants, sellers, offers).
  * Ledger sanity — the anti-gaming ledger must be internally consistent
    (honored_claims<=shipments, checkins_responded<=shipments,
     establishment_confirmed<=checkins_responded).
  * Uniqueness of ids within each file.
  * GOLDEN RANKING — scores the offers through the ONE shared model in
    ../model.js (run via `node`, the same code the browser app runs — no
    hand-copied Python re-implementation to drift), and asserts the seeded gamer
    lab (@tropiflask_wholesale) ranks LAST and a verified lab ranks #1 for the
    Florida Beauty request. This is the core teaching example; a data or
    coefficient change that breaks it is caught. If `node` is not on PATH these
    ranking checks SKIP with a warning; every pure-data check still runs.
  * BUYER NEEDS shape the ranking — the request's target quantity, budget and
    deadline are no longer decorative (audit finding #4). Golden cases assert
    (a) the seed request's real needs do NOT break gamer-last, and (b) changing
    only the request flips the winner (want 1 -> a sure single plant; want 4+ under
    a budget -> an in-budget multi-plantlet cup), with the gamer still LAST — i.e.
    target/budget move the ranking without letting a low-trust lab buy its way up.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(HERE, "..", "data"))

# Collected failure messages; empty == PASS.
ERRORS = []
# Collected non-fatal notes (printed but do not fail the build).
WARNINGS = []


def fail(msg):
    ERRORS.append(msg)


def load(name):
    path = os.path.join(DATA_DIR, name + ".json")
    if not os.path.exists(path):
        fail("MISSING FILE: %s does not exist" % path)
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as e:
        fail("MALFORMED JSON in %s.json: %s" % (name, e))
        return None


def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


# ---------------------------------------------------------------------------
# Structural checks
# ---------------------------------------------------------------------------

def check_unique_ids(rows, name):
    if not isinstance(rows, list):
        fail("%s.json: expected a JSON array, got %s" % (name, type(rows).__name__))
        return
    seen = set()
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            fail("%s.json[%d]: expected an object, got %s" % (name, i, type(r).__name__))
            continue
        rid = r.get("id")
        if rid is None:
            fail("%s.json[%d]: missing 'id'" % (name, i))
            continue
        if rid in seen:
            fail("%s.json: duplicate id %r" % (name, rid))
        seen.add(rid)


def check_plants(plants):
    for p in plants or []:
        pid = p.get("id", "<no id>")
        for f in ("id", "common_name", "latin_name"):
            if not isinstance(p.get(f), str) or not p.get(f):
                fail("plant %r: missing/empty string field %r" % (pid, f))
        # 'hue'/'leaves' — the catalog art invariants (index.html leafSVG).
        hue = p.get("hero_hue")
        if not isinstance(hue, str) or not hue.startswith("#"):
            fail("plant %r: hero_hue must be a #rrggbb string, got %r" % (pid, hue))
        leaves = p.get("hero_leaves")
        if not is_int(leaves) or leaves < 1:
            fail("plant %r: hero_leaves must be an int >= 1, got %r" % (pid, leaves))


def check_sellers(sellers):
    for s in sellers or []:
        sid = s.get("id", "<no id>")
        if not isinstance(s.get("handle"), str) or not s.get("handle"):
            fail("seller %r: missing/empty 'handle'" % sid)
        for f in ("contamination_rate_claimed", "deflask_success_rate_claimed"):
            v = s.get(f)
            if not is_num(v) or not (0.0 <= v <= 1.0):
                fail("seller %r: %s must be a number in [0,1], got %r" % (sid, f, v))
        lg = s.get("ledger")
        if not isinstance(lg, dict):
            fail("seller %r: missing 'ledger' object" % sid)
            continue
        for f in ("shipments", "honored_claims", "filed_claims",
                  "checkins_responded", "establishment_confirmed"):
            v = lg.get(f)
            if not is_int(v) or v < 0:
                fail("seller %r: ledger.%s must be an int >= 0, got %r" % (sid, f, v))
        # Ledger sanity — the anti-gaming data must be internally consistent.
        # Guard only if the five fields are individually valid ints.
        if all(is_int(lg.get(f)) for f in
               ("shipments", "honored_claims", "filed_claims",
                "checkins_responded", "establishment_confirmed")):
            # honored_claims <= filed_claims <= shipments — witnessed contamination
            # comes from FILED claims; a lab can't honor more than were filed, and
            # can't have more filed than it shipped.
            if lg["honored_claims"] > lg["filed_claims"]:
                fail("seller %r: ledger honored_claims (%d) > filed_claims (%d)"
                     % (sid, lg["honored_claims"], lg["filed_claims"]))
            if lg["filed_claims"] > lg["shipments"]:
                fail("seller %r: ledger filed_claims (%d) > shipments (%d)"
                     % (sid, lg["filed_claims"], lg["shipments"]))
            if lg["honored_claims"] > lg["shipments"]:
                fail("seller %r: ledger honored_claims (%d) > shipments (%d)"
                     % (sid, lg["honored_claims"], lg["shipments"]))
            if lg["checkins_responded"] > lg["shipments"]:
                fail("seller %r: ledger checkins_responded (%d) > shipments (%d)"
                     % (sid, lg["checkins_responded"], lg["shipments"]))
            if lg["establishment_confirmed"] > lg["checkins_responded"]:
                fail("seller %r: ledger establishment_confirmed (%d) > "
                     "checkins_responded (%d)"
                     % (sid, lg["establishment_confirmed"], lg["checkins_responded"]))


VALID_STAGES = {"invitro", "deflasked", "acclimated"}


def check_offers(offers, plant_ids, seller_ids):
    for o in offers or []:
        oid = o.get("id", "<no id>")
        # Referential integrity.
        if o.get("plant_id") not in plant_ids:
            fail("offer %r: plant_id %r not found in plants.json"
                 % (oid, o.get("plant_id")))
        if o.get("seller_id") not in seller_ids:
            fail("offer %r: seller_id %r not found in sellers.json"
                 % (oid, o.get("seller_id")))
        # Required fields / ranges.
        stage = o.get("stage")
        if stage not in VALID_STAGES:
            fail("offer %r: stage must be one of %s, got %r"
                 % (oid, sorted(VALID_STAGES), stage))
        ppc = o.get("plantlets_per_cup")
        if not is_int(ppc) or ppc < 1:
            fail("offer %r: plantlets_per_cup must be an int >= 1, got %r" % (oid, ppc))
        for f in ("price", "shipping"):
            v = o.get(f)
            if not is_num(v) or v < 0:
                fail("offer %r: %s must be a number >= 0, got %r" % (oid, f, v))
        specs = o.get("specs")
        if not isinstance(specs, dict):
            fail("offer %r: missing 'specs' object" % oid)
            continue
        ps = specs.get("phenotype_stability")
        if not is_num(ps) or not (0 <= ps <= 100):
            fail("offer %r: specs.phenotype_stability must be a number in [0,100], "
                 "got %r" % (oid, ps))


def check_reviews(reviews, plant_ids, seller_ids):
    for r in reviews or []:
        rid = r.get("id", "<no id>")
        if r.get("seller_id") not in seller_ids:
            fail("review %r: seller_id %r not found in sellers.json"
                 % (rid, r.get("seller_id")))
        # plant_id is optional in the schema spirit, but present on all rows;
        # if present it must resolve.
        if r.get("plant_id") is not None and r.get("plant_id") not in plant_ids:
            fail("review %r: plant_id %r not found in plants.json"
                 % (rid, r.get("plant_id")))
        stars = r.get("stars")
        if not is_num(stars) or not (0 <= stars <= 5):
            fail("review %r: stars must be a number in [0,5], got %r" % (rid, stars))


def check_requests(requests, plant_ids):
    if not requests:
        fail("requests.json: expected at least the seed request, got none")
        return
    for req in requests:
        qid = req.get("id", "<no id>")
        if req.get("plant_id") not in plant_ids:
            fail("request %r: plant_id %r not found in plants.json"
                 % (qid, req.get("plant_id")))


# ---------------------------------------------------------------------------
# GOLDEN RANKING — computed by the ONE model in ../model.js, run through node.
# This validator no longer re-implements the survival/trust/score math (it used
# to, "kept in sync by hand"); it shells the real model out to node so a data or
# coefficient change is scored by the exact code the browser app runs. If node is
# unavailable the golden/churn/unit checks SKIP (with a warning) and all the pure-
# data checks above still run and gate the build.
# ---------------------------------------------------------------------------

import shutil
import subprocess

MODEL_PATH = os.path.normpath(os.path.join(HERE, "..", "model.js"))
GOLDEN_PLANT = "philo-florida-beauty-tc"
GOLDEN_SKILL = "some"           # index.html default buyer skill
GAMER_HANDLE = "@tropiflask_wholesale"
CONTAM_PRIOR = 0.10             # must match model.js (asserted below, not recomputed)

# Tiny node driver: require the shared model, read a JSON job from stdin, and
# print the ranked offers back. Two job shapes:
#   {"offers":[...], "sellers":[...], "skill":"some", "needs":{...}?} -> enrich()+recompute()
#   {"enriched":[...], "skill":"some", "needs":{...}?}                -> recompute() only (fixtures)
# `needs` (optional) is the NUMERIC buyer needs {target,budget,deadline} the
# ranking now folds in (target quantity fit + soft budget penalty + deadline flag);
# omit it and the ranking behaves exactly as before that feature (graceful default).
NODE_DRIVER = r"""
const PP = require(process.argv[1]);
let raw = "";
process.stdin.on("data", d => raw += d);
process.stdin.on("end", () => {
  const p = JSON.parse(raw);
  let arr;
  if (p.enriched) { arr = p.enriched; }
  else {
    const byId = {};
    (p.sellers || []).forEach(s => { byId[s.id] = s; });
    arr = (p.offers || []).map(o => PP.enrich(o, byId[o.seller_id] || {}));
  }
  PP.recompute(arr, p.skill, p.needs || {});
  process.stdout.write(JSON.stringify(arr.map(o => ({
    id: o.id, handle: o.handle, confidence: o.confidence,
    contam: o.contam, contam_deflask: o.contam_deflask,
    _score: o._score, _lt: o._lt,
    pAtLeastOne: (o._s ? o._s.pAtLeastOne : null),
    expLive: (o._s ? o._s.expLive : null),
    overBudget: !!o._overBudget, overBudgetBy: o._overBudgetBy,
    targetFit: o._targetFit, meetsTarget: o._meetsTarget, lateEta: !!o._lateEta
  }))));
});
"""


def find_node():
    """Return a node executable path, or None if node isn't on PATH."""
    return shutil.which("node") or shutil.which("nodejs")


def rank_via_node(node, payload):
    """Rank `payload` through ../model.js via node; return the ranked list of
    dicts, or None (and record a failure) if the subprocess errors."""
    try:
        proc = subprocess.run(
            [node, "-e", NODE_DRIVER, MODEL_PATH],
            input=json.dumps(payload), capture_output=True, text=True, timeout=30)
    except Exception as e:  # pragma: no cover - environment failure
        fail("golden ranking: could not run node model (%s)" % e)
        return None
    if proc.returncode != 0:
        fail("golden ranking: node model exited %d: %s"
             % (proc.returncode, (proc.stderr or "").strip()))
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        fail("golden ranking: node model returned non-JSON (%s): %r"
             % (e, proc.stdout[:200]))
        return None


def check_golden_ranking(node, offers, sellers):
    pool = [o for o in offers if o.get("plant_id") == GOLDEN_PLANT]
    if not pool:
        fail("golden ranking: no offers found for %r — the seeded Florida Beauty "
             "teaching example is gone" % GOLDEN_PLANT)
        return None
    ranked = rank_via_node(node, {"offers": pool, "sellers": sellers,
                                  "skill": GOLDEN_SKILL})
    if ranked is None:
        return None
    order = [eo["handle"] for eo in ranked]

    winner = order[0]
    loser = order[-1]

    if loser != GAMER_HANDLE:
        fail("golden ranking: gamer lab %s expected LAST but ranked %d/%d "
             "(last place went to %s). Full order: %s"
             % (GAMER_HANDLE, order.index(GAMER_HANDLE) + 1
                if GAMER_HANDLE in order else -1,
                len(order), loser, order))
    # Winner must be a genuinely verified/certified lab, not the gamer.
    winner_seller = next((s for s in sellers if s.get("handle") == winner), None)
    winner_certs = len(winner_seller.get("certs") or []) if winner_seller else 0
    if winner == GAMER_HANDLE or winner_certs == 0:
        fail("golden ranking: #1 %s is not a verified/certified lab "
             "(certs=%d). The 'trust beats a cheap gamer' lesson is broken."
             % (winner, winner_certs))

    # Load-bearing property the ranking depends on: the gamer's LEDGER-derived
    # contamination must be far worse than its self-reported claim. (Pure data —
    # no model needed.)
    gamer = next((s for s in sellers if s.get("handle") == GAMER_HANDLE), None)
    if gamer:
        lg = gamer.get("ledger") or {}
        filed = lg.get("filed_claims", lg.get("honored_claims"))
        if lg.get("shipments") and filed is not None:
            witnessed = filed / lg["shipments"]   # witnessed = FILED / shipments
            claimed = gamer.get("contamination_rate_claimed", 0)
            if not (witnessed >= claimed * 3):
                fail("golden ranking: gamer %s witnessed contamination "
                     "(%.3f) is not materially worse than its claim (%.3f); "
                     "the anti-gaming signal has been neutered."
                     % (GAMER_HANDLE, witnessed, claimed))
    return order


def check_churn_attack(node, offers, sellers):
    """GOLDEN CASE (a): the churn attack must FAIL. A gamer that re-registers with
    NO ledger and claims a spotless 0% contamination / 100% deflask cannot reach
    the #1 slot while any ledger-backed offer exists — even priced to undercut."""
    pool = [o for o in offers if o.get("plant_id") == GOLDEN_PLANT]
    if not pool:
        return
    # A brand-new, ledgerless clone of the gamer making the perfect claim, cheap.
    churn_seller = {
        "id": "_churn_clone", "handle": "@tropiflask_reborn",
        "rating": 5.0, "sales_count": 3, "certs": [],
        "contamination_rate_claimed": 0.0, "deflask_success_rate_claimed": 1.0,
        "ledger": None,  # <-- the attack: no witnessed outcomes
        "replacement_policy": {"covers": True},
    }
    churn_offer = {
        "id": "_churn_offer", "plant_id": GOLDEN_PLANT, "seller_id": "_churn_clone",
        "stage": "deflasked", "plantlets_per_cup": 5, "price": 1, "shipping": 0,
    }
    ranked = rank_via_node(node, {"offers": pool + [churn_offer],
                                  "sellers": sellers + [churn_seller],
                                  "skill": GOLDEN_SKILL})
    if ranked is None:
        return

    # The clone must NOT be #1, and #1 must be ledger-backed (not unverified).
    if ranked[0]["id"] == "_churn_offer":
        fail("churn attack: a no-ledger lab claiming 0%%/100%% reached #1 — the "
             "anti-gaming #1-slot rule failed.")
    if ranked[0].get("confidence") == "unverified":
        fail("churn attack: #1 offer %r is unverified (no ledger) — a lab with no "
             "witnessed outcomes must never hold #1." % ranked[0]["id"])
    # And its ledgerless contamination must be pinned to (not better than) the prior.
    clone = next((o for o in ranked if o["id"] == "_churn_offer"), None)
    if clone and clone["contam"] < CONTAM_PRIOR:
        fail("churn attack: no-ledger clone contam %.3f is better than the prior "
             "%.3f — an unproven claim was trusted." % (clone["contam"], CONTAM_PRIOR))

    # ANTI-GAMING under the new needs objective: a quantity-maximising request must
    # NOT let the cheap ledgerless clone (a 5-plantlet cup) buy the #1 slot by
    # hitting the target count. Re-rank with an aggressive "as many as possible /
    # any price" need and assert the #1-slot rule still holds.
    ranked_qty = rank_via_node(node, {"offers": pool + [churn_offer],
                                      "sellers": sellers + [churn_seller],
                                      "skill": GOLDEN_SKILL,
                                      "needs": {"target": 8, "budget": None,
                                                "deadline": None}})
    if ranked_qty is not None:
        if ranked_qty[0]["id"] == "_churn_offer":
            fail("churn attack (quantity request): the ledgerless 5-plantlet clone "
                 "reached #1 by hitting the target count — target fit let an "
                 "unverified lab buy its way up. Anti-gaming failed.")
        if ranked_qty[0].get("confidence") == "unverified":
            fail("churn attack (quantity request): #1 is unverified — the #1-slot "
                 "rule failed under a target-quantity need.")


def check_needs_shape_ranking(node):
    """GOLDEN CASE (target/budget): the buyer's STATED NEEDS must actually move the
    ranking — they used to be decorative (audit finding #4). On ONE fixed pool of
    three offers, changing only the request flips the winner:

      * Request A — "just 1 live plant, best odds regardless of price"
        (target=1, no budget): the sure single ACCLIMATED plant from a top lab wins.
      * Request B — "a few (4+) live plants, under $40"
        (target=4, budget=40): the IN-BUDGET multi-plantlet cup from a trusted lab
        wins, and the (now over-budget) single acclimated plant is demoted AND
        flagged over budget.

    In BOTH requests the seeded gamer clone ranks LAST — proving target/budget move
    the ranking WITHOUT letting a low-trust lab buy its way up on plantlet count."""
    single_lab = {
        "id": "_trusted_single", "handle": "@trusted_single",
        "rating": 4.85, "sales_count": 200, "certs": ["Verified lab", "Sterile-lab certified"],
        "contamination_rate_claimed": 0.02, "deflask_success_rate_claimed": 0.96,
        "ledger": {"shipments": 190, "honored_claims": 4, "filed_claims": 5,
                   "checkins_responded": 140, "establishment_confirmed": 134},
        "replacement_policy": {"covers": True},
    }
    multi_lab = {
        "id": "_trusted_multi", "handle": "@trusted_multi",
        "rating": 4.4, "sales_count": 90, "certs": ["Verified lab"],
        "contamination_rate_claimed": 0.08, "deflask_success_rate_claimed": 0.75,
        "ledger": {"shipments": 90, "honored_claims": 6, "filed_claims": 9,
                   "checkins_responded": 100, "establishment_confirmed": 40},
        "replacement_policy": {"covers": True},
    }
    gamer_lab = {
        "id": "_gamer", "handle": GAMER_HANDLE,
        "rating": 3.8, "sales_count": 41, "certs": [],
        "contamination_rate_claimed": 0.02, "deflask_success_rate_claimed": 0.90,
        "ledger": {"shipments": 240, "honored_claims": 48, "filed_claims": 60,
                   "checkins_responded": 150, "establishment_confirmed": 70},
        "replacement_policy": {"covers": False},
    }
    sellers = [single_lab, multi_lab, gamer_lab]
    o_single = {"id": "o_single", "plant_id": "p", "seller_id": "_trusted_single",
                "stage": "acclimated", "plantlets_per_cup": 1, "price": 38,
                "shipping": 8, "eta_days": 4}
    o_multi = {"id": "o_multi", "plant_id": "p", "seller_id": "_trusted_multi",
               "stage": "invitro", "plantlets_per_cup": 6, "price": 22,
               "shipping": 8, "eta_days": 5}
    o_gamer = {"id": "o_gamer", "plant_id": "p", "seller_id": "_gamer",
               "stage": "invitro", "plantlets_per_cup": 6, "price": 18,
               "shipping": 9, "eta_days": 6}
    offers = [o_single, o_multi, o_gamer]

    need_a = {"target": 1, "budget": None, "deadline": None}
    need_b = {"target": 4, "budget": 40, "deadline": None}
    ra = rank_via_node(node, {"offers": offers, "sellers": sellers,
                              "skill": GOLDEN_SKILL, "needs": need_a})
    rb = rank_via_node(node, {"offers": offers, "sellers": sellers,
                              "skill": GOLDEN_SKILL, "needs": need_b})
    if ra is None or rb is None:
        return
    ord_a = [o["id"] for o in ra]
    ord_b = [o["id"] for o in rb]

    # Request A: the sure single plant wins when the buyer wants just 1 at any price.
    if ord_a[0] != "o_single":
        fail("needs case A ('just 1, any price'): expected the single acclimated "
             "plant #1, got %s. Order: %s" % (ord_a[0], ord_a))
    # Request B: the in-budget multi cup wins when the buyer wants 4+ under $40.
    if ord_b[0] != "o_multi":
        fail("needs case B ('want 4+, under $40'): expected the in-budget multi "
             "cup #1, got %s. Order: %s" % (ord_b[0], ord_b))
    # The needs actually MOVED the ranking (different winner for A vs B).
    if ord_a[0] == ord_b[0]:
        fail("needs cases: the winner did not change between 'want 1 / any price' "
             "and 'want 4+ / under $40' — target/budget are still decorative.")
    # The over-budget single must be demoted below the in-budget multi AND flagged.
    single_b = next((o for o in rb if o["id"] == "o_single"), None)
    if single_b is not None and not single_b.get("overBudget"):
        fail("needs case B: the $46 single is not flagged over budget for a $40 "
             "budget — the over-budget flag is not being set.")
    # Anti-gaming preserved: the gamer clone is LAST in BOTH requests.
    for label, order in (("A", ord_a), ("B", ord_b)):
        if order[-1] != "o_gamer":
            fail("needs case %s: gamer expected LAST but ranked %d/%d (order=%s). "
                 "A low-trust lab must not climb via quantity/budget."
                 % (label, order.index("o_gamer") + 1, len(order), order))
    return ord_a, ord_b


def check_seed_needs_gamer_last(node, offers, sellers):
    """The seeded Florida Beauty request carries REAL needs (target '2–3', budget
    '$70', deadline 'next week'). Folding those needs into the ranking must NOT
    break the anti-gaming invariant: the gamer still ranks LAST and #1 is still a
    verified/certified lab. (Guards the case where target quantity could otherwise
    lift the gamer's cheap 6-plantlet cup.)"""
    pool = [o for o in offers if o.get("plant_id") == GOLDEN_PLANT]
    if not pool:
        return
    # parseNeeds equivalent for the seed request's notes.
    seed_needs = {"target": 3, "budget": 70, "deadline": 7}
    ranked = rank_via_node(node, {"offers": pool, "sellers": sellers,
                                  "skill": GOLDEN_SKILL, "needs": seed_needs})
    if ranked is None:
        return
    order = [o["handle"] for o in ranked]
    if order[-1] != GAMER_HANDLE:
        fail("seed-needs ranking: with the seed request's real needs (2-3 / $70 / "
             "next week) the gamer %s expected LAST but ranked %d/%d (order=%s)."
             % (GAMER_HANDLE, order.index(GAMER_HANDLE) + 1 if GAMER_HANDLE in order
                else -1, len(order), order))
    if ranked[0].get("confidence") == "unverified" or order[0] == GAMER_HANDLE:
        fail("seed-needs ranking: #1 %s is not a verified lab under the seed needs."
             % order[0])


def check_rank_rule_unit(node):
    """Direct unit check of the #1-slot rule: even when an unverified offer has the
    single highest score, recompute() must demote it below a ledger-backed one.
    Feeds pre-enriched fixtures straight to the shared model via node."""
    top_unverified = {"id": "u", "confidence": "unverified", "stage": "acclimated",
                      "plantlets": 1, "price": 1, "shipping": 0, "replace": True,
                      "rating": 5, "sales": 500, "certsCount": 2, "contam": 0.10,
                      "contam_deflask": 0.65, "honorRate": None}
    verified = {"id": "v", "confidence": "verified", "stage": "acclimated",
                "plantlets": 1, "price": 60, "shipping": 10, "replace": True,
                "rating": 4.9, "sales": 400, "certsCount": 2, "contam": 0.03,
                "contam_deflask": 0.9, "honorRate": 0.9}
    # Score each fixture alone so we can confirm the unverified one really does
    # out-score the verified one (i.e. the demotion path is exercised).
    solo_u = rank_via_node(node, {"enriched": [dict(top_unverified)],
                                  "skill": GOLDEN_SKILL})
    solo_v = rank_via_node(node, {"enriched": [dict(verified)],
                                  "skill": GOLDEN_SKILL})
    if solo_u and solo_v and not solo_u[0]["_score"] > solo_v[0]["_score"]:
        WARNINGS.append("rank-rule unit: unverified fixture did not out-score "
                        "verified; test is not exercising the demotion path")
    ranked = rank_via_node(node, {"enriched": [dict(top_unverified), dict(verified)],
                                  "skill": GOLDEN_SKILL})
    if ranked is None:
        return
    if ranked[0]["id"] != "v":
        fail("rank-rule unit: an unverified offer held #1 over a verified one "
             "despite the anti-gaming rule (order=%s)." % [o["id"] for o in ranked])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    plants = load("plants")
    sellers = load("sellers")
    offers = load("offers")
    reviews = load("reviews")
    requests = load("requests")

    # If any file failed to load/parse, bail with what we have (fail already set).
    for name, rows in (("plants", plants), ("sellers", sellers),
                       ("offers", offers), ("reviews", reviews),
                       ("requests", requests)):
        if rows is not None:
            check_unique_ids(rows, name)

    plant_ids = {p.get("id") for p in plants} if isinstance(plants, list) else set()
    seller_ids = {s.get("id") for s in sellers} if isinstance(sellers, list) else set()

    if isinstance(plants, list):
        check_plants(plants)
    if isinstance(sellers, list):
        check_sellers(sellers)
    if isinstance(offers, list):
        check_offers(offers, plant_ids, seller_ids)
    if isinstance(reviews, list):
        check_reviews(reviews, plant_ids, seller_ids)
    if isinstance(requests, list):
        check_requests(requests, plant_ids)

    golden_order = None
    # Only attempt the golden ranking if the core data structurally loaded. The
    # model is ../model.js run through node; if node is missing we SKIP these three
    # checks (with a warning) rather than hard-fail — the pure-data checks above
    # already ran and gate the build.
    if isinstance(offers, list) and isinstance(sellers, list) and not ERRORS:
        node = find_node()
        if node:
            golden_order = check_golden_ranking(node, offers, sellers)
            check_churn_attack(node, offers, sellers)  # golden case (a): churn attack fails
            check_seed_needs_gamer_last(node, offers, sellers)  # anti-gaming holds under real seed needs
            check_needs_shape_ranking(node)            # golden case (b): target/budget move the ranking
            check_rank_rule_unit(node)                 # unit: #1-slot rule demotes unverified
        else:
            WARNINGS.append("node not found on PATH — SKIPPED the golden-ranking, "
                            "churn-attack and rank-rule checks (they run ../model.js "
                            "via node). Pure-data checks above still ran and gate the "
                            "build. Install node to exercise the ranking model.")

    print("=" * 64)
    if ERRORS:
        print("plantpeers data validation: FAIL (%d problem%s)"
              % (len(ERRORS), "" if len(ERRORS) == 1 else "s"))
        print("-" * 64)
        for e in ERRORS:
            print("  FAIL: " + e)
        print("=" * 64)
        return 1

    print("plantpeers data validation: PASS")
    print("-" * 64)
    print("  plants   checked: %d" % (len(plants) if plants else 0))
    print("  sellers  checked: %d (ledger sanity ok: honored<=filed<=shipments)"
          % (len(sellers) if sellers else 0))
    print("  offers   checked: %d (refs + fields + ranges ok)"
          % (len(offers) if offers else 0))
    print("  reviews  checked: %d (refs ok)" % (len(reviews) if reviews else 0))
    print("  requests checked: %d (seed plant_id resolves)"
          % (len(requests) if requests else 0))
    if golden_order:
        print("  golden ranking (Florida Beauty, skill=%s):" % GOLDEN_SKILL)
        print("    #1  %s   (verified/certified lab)" % golden_order[0])
        print("    ... ")
        print("    #%d  %s   (seeded gamer lab, correctly LAST)"
              % (len(golden_order), golden_order[-1]))
        print("  anti-gaming: churn attack fails (#1-slot rule, incl. quantity "
              "request) · gamer LAST under seed needs · unverified-demotion unit ok")
        print("  buyer needs: target/budget move the ranking (want-1 -> single "
              "wins; want-4+/under-$40 -> in-budget multi wins), gamer still last")
    for w in WARNINGS:
        print("  note: " + w)
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
