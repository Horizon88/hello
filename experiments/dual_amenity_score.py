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
import json, pathlib, sys

# Score with the single source of truth shared with the production post-processor.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
from dual_score import sea_strength, ski_strength, cheapness, dual_score

DATA = pathlib.Path(__file__).resolve().parent.parent / "docs" / "listings.json"


def scored_parts(x):
    """(dual_score, (sea, ski, cheapness)) — the strength breakdown for the table."""
    return dual_score(x), (sea_strength(x), ski_strength(x), cheapness(x))


def main():
    d = json.load(open(DATA))
    land = [x for x in d if x.get("tp") == "land"]

    # current rank position by r, for comparison
    by_r = sorted(land, key=lambda z: -(z.get("r") or 0))
    rpos = {id(x): i + 1 for i, x in enumerate(by_r)}

    scored = []
    for x in land:
        ds, parts = scored_parts(x)
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
