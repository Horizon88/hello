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
  * GOLDEN RANKING — replicates the survival/labTrust/betaMean/score model from
    index.html and asserts the seeded gamer lab (@tropiflask_wholesale) ranks
    LAST and a verified lab ranks #1 for the Florida Beauty request. This is the
    core teaching example; a data or coefficient change that breaks it is caught.
"""

import json
import math
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
# GOLDEN RANKING — faithful re-implementation of the index.html model.
# Keep these coefficients in sync with index.html; this check exists precisely
# to fail if they (or the data) drift and break the core teaching example.
# ---------------------------------------------------------------------------

SKILL = {"beg": 0.65, "some": 0.85, "pro": 1.0}
CONTAM_PRIOR, CONTAM_STRENGTH = 0.10, 25
DEFLASK_PRIOR, DEFLASK_STRENGTH = 0.65, 20
GOLDEN_PLANT = "philo-florida-beauty-tc"
GOLDEN_SKILL = "some"           # index.html default buyer skill
GAMER_HANDLE = "@tropiflask_wholesale"


def beta_mean(k, n, prior_rate, strength):
    a0 = prior_rate * strength
    b0 = (1 - prior_rate) * strength
    return (a0 + k) / (a0 + b0 + n)


def confidence_tier(shipments, checkins):
    if shipments >= 60 and checkins >= 40:
        return "verified"
    if shipments >= 20:
        return "thin"
    return "unverified"


def enrich(offer, seller):
    o = {}
    lg = seller.get("ledger")
    if lg and lg.get("shipments", 0) > 0 and lg.get("checkins_responded", 0) > 0:
        # witnessed contamination from FILED claims (denying claims can't hide it)
        filed = lg["filed_claims"] if lg.get("filed_claims") is not None \
            else lg["honored_claims"]
        o["honorRate"] = (lg["honored_claims"] / filed) if filed > 0 else 1.0
        o["confidence"] = confidence_tier(lg["shipments"], lg["checkins_responded"])
        o["contam"] = beta_mean(filed, lg["shipments"],
                                CONTAM_PRIOR, CONTAM_STRENGTH)
        o["contam_deflask"] = beta_mean(lg["establishment_confirmed"],
                                        lg["checkins_responded"],
                                        DEFLASK_PRIOR, DEFLASK_STRENGTH)
        if o["confidence"] == "unverified":
            # thin ledger: pin to prior, never better than the cautious prior
            o["contam"] = max(CONTAM_PRIOR, o["contam"])
            o["contam_deflask"] = min(DEFLASK_PRIOR, o["contam_deflask"])
    else:
        # no ledger (churned lab): pin to prior, do NOT trust the raw claim
        o["confidence"] = "unverified"
        o["honorRate"] = None
        o["contam"] = max(CONTAM_PRIOR,
                          seller.get("contamination_rate_claimed", 0.15))
        o["contam_deflask"] = min(DEFLASK_PRIOR,
                                  seller.get("deflask_success_rate_claimed", 0.6))
    rp = seller.get("replacement_policy") or {}
    o["replace"] = bool(rp.get("covers"))
    o["rating"] = seller.get("rating", 0) or 0
    o["sales"] = seller.get("sales_count", 0) or 0
    o["certsCount"] = len(seller.get("certs") or [])
    o["stage"] = offer.get("stage")
    o["plantlets"] = offer.get("plantlets_per_cup", 1)
    o["price"] = offer.get("price", 0)
    o["shipping"] = offer.get("shipping", 0)
    o["id"] = offer.get("id")
    o["handle"] = seller.get("handle")
    return o


def survival(o, skill):
    sk = SKILL[skill]
    if o["stage"] == "invitro":
        per_plant = o["contam_deflask"] * sk
    elif o["stage"] == "deflasked":
        per_plant = 0.80 + 0.18 * o["contam_deflask"]   # lab establishment shows through
    else:
        per_plant = 0.90 + 0.09 * o["contam_deflask"]   # acclimated: ledger nudges
    eff_contam = o["contam"] * 0.15 if o["replace"] else o["contam"]
    # acclimated already in soil — cup contamination risk retired
    p_clean = 1.0 if o["stage"] == "acclimated" else (1 - eff_contam)
    n = o["plantlets"]
    p_at_least_one = p_clean * (1 - math.pow(1 - per_plant, n))
    exp_live = p_clean * n * per_plant
    total = o["price"] + o["shipping"]
    cost_per_live = total / exp_live if exp_live > 0 else 999
    return {"pAtLeastOne": p_at_least_one, "costPerLive": cost_per_live}


def lab_trust(o):
    contam_score = max(0, 1 - o["contam"] / 0.25)
    deflask_score = o["contam_deflask"]
    rating_score = o["rating"] / 5
    vol_score = min(1, math.log10(o["sales"] + 1) / math.log10(500))
    cert_score = min(1, o["certsCount"] / 2)
    honor_score = o["honorRate"] if o.get("honorRate") is not None else 0.85
    raw = (0.30 * contam_score + 0.18 * deflask_score + 0.12 * rating_score
           + 0.08 * vol_score + 0.10 * cert_score
           + 0.10 * (1 if o["replace"] else 0) + 0.12 * honor_score)
    return round(raw * 100)


def score(o, skill):
    s = survival(o, skill)
    surv_score = s["pAtLeastOne"] * 100
    price_score = max(0, min(100, 100 - (s["costPerLive"] - 15) * 1.5))
    lt = lab_trust(o)
    return 0.45 * surv_score + 0.35 * lt + 0.20 * price_score


def rank_eligible_for_top(o):
    """An offer can hold #1 only if it has witnessed outcomes (real ledger)."""
    return o.get("confidence") != "unverified"


def rank_offers(enriched, skill):
    """Score-sort desc, then apply the anti-gaming #1-slot rule: an unverified
    (no/thin-ledger) offer cannot rank first while any ledger-backed offer exists."""
    ranked = sorted(enriched, key=lambda o: score(o, skill), reverse=True)
    if len(ranked) >= 2 and not rank_eligible_for_top(ranked[0]):
        for i in range(1, len(ranked)):
            if rank_eligible_for_top(ranked[i]):
                ranked.insert(0, ranked.pop(i))
                break
    return ranked


def check_golden_ranking(offers, sellers):
    sellers_by_id = {s["id"]: s for s in sellers}
    pool = [o for o in offers if o.get("plant_id") == GOLDEN_PLANT]
    if not pool:
        fail("golden ranking: no offers found for %r — the seeded Florida Beauty "
             "teaching example is gone" % GOLDEN_PLANT)
        return None
    enriched = []
    for o in pool:
        s = sellers_by_id.get(o.get("seller_id"))
        if not s:
            return None  # referential check already reported this
        enriched.append(enrich(o, s))
    ranked = rank_offers(enriched, GOLDEN_SKILL)
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
    # contamination must be far worse than its self-reported claim.
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


def check_churn_attack(offers, sellers):
    """GOLDEN CASE (a): the churn attack must FAIL. A gamer that re-registers with
    NO ledger and claims a spotless 0% contamination / 100% deflask cannot reach
    the #1 slot while any ledger-backed offer exists — even priced to undercut."""
    sellers_by_id = {s["id"]: s for s in sellers}
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
    enriched = [enrich(o, sellers_by_id[o["seller_id"]]) for o in pool
                if o.get("seller_id") in sellers_by_id]
    enriched.append(enrich(churn_offer, churn_seller))
    ranked = rank_offers(enriched, GOLDEN_SKILL)

    # The clone must NOT be #1, and #1 must be ledger-backed (not unverified).
    if ranked[0]["id"] == "_churn_offer":
        fail("churn attack: a no-ledger lab claiming 0%%/100%% reached #1 — the "
             "anti-gaming #1-slot rule failed.")
    if not rank_eligible_for_top(ranked[0]):
        fail("churn attack: #1 offer %r is unverified (no ledger) — a lab with no "
             "witnessed outcomes must never hold #1." % ranked[0]["id"])
    # And its ledgerless contamination must be pinned to (not better than) the prior.
    clone = next((o for o in enriched if o["id"] == "_churn_offer"), None)
    if clone and clone["contam"] < CONTAM_PRIOR:
        fail("churn attack: no-ledger clone contam %.3f is better than the prior "
             "%.3f — an unproven claim was trusted." % (clone["contam"], CONTAM_PRIOR))


def check_rank_rule_unit():
    """Direct unit check of the #1-slot rule: even when an unverified offer has the
    single highest score, rank_offers must demote it below a ledger-backed one."""
    top_unverified = {"id": "u", "confidence": "unverified", "stage": "acclimated",
                      "plantlets": 1, "price": 1, "shipping": 0, "replace": True,
                      "rating": 5, "sales": 500, "certsCount": 2, "contam": 0.10,
                      "contam_deflask": 0.65, "honorRate": None}
    verified = {"id": "v", "confidence": "verified", "stage": "acclimated",
                "plantlets": 1, "price": 60, "shipping": 10, "replace": True,
                "rating": 4.9, "sales": 400, "certsCount": 2, "contam": 0.03,
                "contam_deflask": 0.9, "honorRate": 0.9}
    # Sanity: the unverified one really does out-score the verified one.
    if not score(top_unverified, GOLDEN_SKILL) > score(verified, GOLDEN_SKILL):
        WARNINGS.append("rank-rule unit: unverified fixture did not out-score "
                        "verified; test is not exercising the demotion path")
    ranked = rank_offers([top_unverified, verified], GOLDEN_SKILL)
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
    # Only attempt the golden ranking if the core data structurally loaded.
    if isinstance(offers, list) and isinstance(sellers, list) and not ERRORS:
        golden_order = check_golden_ranking(offers, sellers)
        check_churn_attack(offers, sellers)   # golden case (a): churn attack fails
        check_rank_rule_unit()                # unit: #1-slot rule demotes unverified

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
        print("  anti-gaming: churn attack fails (#1-slot rule) · "
              "unverified-demotion unit ok · honor-rate signal live")
    for w in WARNINGS:
        print("  note: " + w)
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
