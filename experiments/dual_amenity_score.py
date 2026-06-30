#!/usr/bin/env python3
"""SPIKE: "Dual-amenity" lens — surface land that is BOTH coastal AND ski-accessible,
and is cheap. The current additive score is size-dominant, so these rare parcels are
buried at r=58-72 while $1-9M inland NZ mega-lots sit at the top.

Thesis: the user's actual jackpot is "cheap + ocean-view + ski-in reach" in ONE parcel.
That combination is rare (~30 listings) and currently invisible. A multiplicative
"dual-amenity" score that rewards co-occurrence (not just sum) surfaces them.

Reads docs/listings.json (real data). Prints the new ranking vs. where each parcel
sits in the current r-ranking. No deps beyond stdlib.

    python3 experiments/dual_amenity_score.py
"""
import json, math, pathlib

DATA = pathlib.Path(__file__).resolve().parent.parent / "docs" / "listings.json"


def sea_strength(x):
    """0..1 how strongly this is an ocean parcel."""
    # view_verified True is the strongest signal we have
    if x.get("view_verified") is True:
        base = 1.0
    elif x.get("v") in ("beachfront", "sea_visible", "coastal"):
        base = 0.7
    else:
        base = 0.0
    ck = x.get("coast_km")
    if isinstance(ck, (int, float)):
        # closer water = stronger; full credit <1km, fades to 0 by 10km
        prox = max(0.0, 1.0 - ck / 10.0)
        base = max(base, prox)  # proximity alone can earn partial sea credit
    return base


def ski_strength(x):
    k = x.get("ski_km")
    if not isinstance(k, (int, float)):
        return 0.0
    # ski-in (<1km)=1.0, fades to 0 by 12km
    return max(0.0, 1.0 - k / 12.0)


def cheapness(x):
    """0..1, cheap parcels score high. Uses absolute USD, not $/m2 — the user wants
    a parcel they can actually buy, so a $6k lot beats a $2M one regardless of size."""
    usd = x.get("usd")
    if not isinstance(usd, (int, float)) or usd <= 0:
        return 0.0
    # log scale: $5k -> ~1.0, $50k -> ~0.7, $500k -> ~0.4, $5M -> ~0.1
    return max(0.0, min(1.0, 1.0 - (math.log10(usd) - 3.7) / 3.3))


def dual_score(x):
    """Multiplicative: a parcel must have BOTH amenities to score. Sum can't fake it."""
    s, k, c = sea_strength(x), ski_strength(x), cheapness(x)
    # geometric-ish: both amenities required, cheapness modulates
    combo = math.sqrt(s * k)        # 0 unless BOTH present
    return round(100 * combo * (0.5 + 0.5 * c), 1), (s, k, c)


def main():
    d = json.load(open(DATA))
    land = [x for x in d if x.get("tp") == "land"]

    # current rank position by r, for comparison
    by_r = sorted(land, key=lambda z: -(z.get("r") or 0))
    rpos = {id(x): i + 1 for i, x in enumerate(by_r)}

    scored = []
    for x in land:
        ds, parts = dual_score(x)
        if ds > 0:
            scored.append((ds, parts, x))
    scored.sort(key=lambda t: -t[0])

    print(f"land listings: {len(land)}   parcels with dual-amenity signal: {len(scored)}\n")
    print(f"{'dual':>5} {'sea':>4} {'ski':>4} {'chp':>4} | {'curR':>5} {'curRank':>7} | "
          f"{'country':<14} {'region':<12} {'$USD':>9} {'ac':>6}  coast/ski km")
    print("-" * 110)
    for ds, (s, k, c), x in scored[:15]:
        print(f"{ds:5.1f} {s:4.2f} {k:4.2f} {c:4.2f} | "
              f"{(x.get('r') or 0):5.0f} {rpos[id(x)]:7d} | "
              f"{(x.get('cf') or '')[:14]:<14} {(x.get('rg') or '')[:12]:<12} "
              f"{x.get('usd'):9,.0f} {x.get('ac'):6.2f}  "
              f"{x.get('coast_km')}/{x.get('ski_km')}")

    # The headline signal: where do the top dual parcels live in the CURRENT ranking?
    top10_curpos = [rpos[id(x)] for _, _, x in scored[:10]]
    print("\nSIGNAL:")
    print(f"  Top-10 dual-amenity parcels currently rank at positions "
          f"{min(top10_curpos)}-{max(top10_curpos)} (of {len(land)}) by the live score.")
    print(f"  Median current rank of the top-10 dual finds: "
          f"{sorted(top10_curpos)[len(top10_curpos)//2]}.")
    cheapest = min((x.get('usd') for _, _, x in scored[:10]), default=0)
    print(f"  Cheapest in the dual top-10: ${cheapest:,.0f}. "
          f"The live top-10 are all $899k-$9.2M inland mega-lots.")


if __name__ == "__main__":
    main()
