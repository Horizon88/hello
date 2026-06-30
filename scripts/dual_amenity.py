#!/usr/bin/env python3
"""Dual-amenity lens — flag the rare parcels that are BOTH coastal AND ski-accessible.

The product's namesake combination ("coastal land + ski mountain") is exactly the
co-occurrence the live size-dominant rating `r` buries: a $6k ski-in/ocean-view lot
in Hokkaido sits at rank ~5,000 while $1-9M inland mega-lots top the board. This is
a LAYER on top of `r`, never a replacement: it sets two fields on qualifying land
rows and leaves everything else (including `r` and the default sort) untouched.

For each land row (`tp == 'land'`) we compute a geometric both-required score: a
parcel with only one of the two amenities scores 0 (a sum can fake it; a product
cannot). Qualifying rows get:

  * `dual`   — boolean True
  * `dual_s` — 0..100 numeric strength

Non-qualifying rows are left untouched (no key written), so the field's presence is
itself the filter signal and re-running is a no-op.

Two guards the prototype flagged are enforced here:

  * Size gate — respect the repo's size-dominant rule. Sub-acre ski-town lots are
    not flagged. Min acreage defaults to 0.5 ac, override with DUAL_MIN_AC.

  * Provenance guard — many Japan/Turkey rows are prefecture- or city-centroid
    geocoded: dozens of distinct listings share one identical (lat, lon), so their
    derived coast_km/ski_km describe the centroid, not the parcel. We detect any
    coordinate shared by >= DUAL_COORD_CLUSTER rows (default 10) and refuse to trust
    those listings' amenity distances. A geocode_src that names a centroid/prefecture
    source is excluded the same way.

Idempotent. Run against both the slim UI file and the full backup so they stay
consistent:

    python3 scripts/dual_amenity.py
"""
from __future__ import annotations

import collections
import json
import os
from pathlib import Path

from dual_score import dual_score

DOCS = Path(__file__).resolve().parent.parent / "docs"
TARGETS = (DOCS / "listings.json", DOCS / "listings.full.json")

# Minimum acreage to be eligible — honours the size-dominant rule (no tiny lots).
MIN_AC = float(os.environ.get("DUAL_MIN_AC", "0.5"))
# A (lat, lon) shared by >= this many rows is treated as a centroid artifact.
COORD_CLUSTER = int(os.environ.get("DUAL_COORD_CLUSTER", "10"))

# geocode_src substrings that mark a row as centroid/region geocoded (best-effort;
# the current dataset leaves geocode_src empty, so the coord-sharing test below is
# the load-bearing guard — this stays for forward compatibility).
CENTROID_SRC_HINTS = ("centroid", "prefecture", "region", "city", "fallback")


def centroid_coords(land):
    """Set of (lat, lon) tuples that are shared by >= COORD_CLUSTER rows."""
    counts = collections.Counter(
        (x.get("lat"), x.get("lon"))
        for x in land
        if x.get("lat") is not None and x.get("lon") is not None
    )
    return {coord for coord, n in counts.items() if n >= COORD_CLUSTER}


def is_centroid_geocoded(x, shared):
    """True if this row's amenity distances can't be trusted (centroid geocoded)."""
    src = x.get("geocode_src")
    if isinstance(src, str) and any(h in src.lower() for h in CENTROID_SRC_HINTS):
        return True
    return (x.get("lat"), x.get("lon")) in shared


def annotate(data):
    """Set / clear `dual` and `dual_s` on land rows in place. Returns flagged count."""
    land = [x for x in data if x.get("tp") == "land"]
    shared = centroid_coords(land)

    flagged = 0
    for x in land:
        # default: ensure no stale flag survives a re-run with changed inputs
        x.pop("dual", None)
        x.pop("dual_s", None)

        if (x.get("ac") or 0) < MIN_AC:
            continue
        if is_centroid_geocoded(x, shared):
            continue
        ds = dual_score(x)
        if ds <= 0:
            continue
        x["dual"] = True
        x["dual_s"] = ds
        flagged += 1
    return flagged, len(land), len(shared)


def write_compact(path, data, was_compact):
    """Write back in the same shape the file already used (slim is minified)."""
    if was_compact:
        out = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    else:
        out = json.dumps(data, ensure_ascii=False)
    path.write_text(out)


def main():
    for path in TARGETS:
        if not path.exists():
            print(f"skip (not found): {path}")
            continue
        raw = path.read_text()
        data = json.loads(raw)
        # slim file is minified (no ", " after separators); preserve that.
        was_compact = ', ' not in raw[:4096]
        before_rows = len(data)
        flagged, land, clusters = annotate(data)
        write_compact(path, data, was_compact)
        assert len(data) == before_rows, "row count changed — refusing"
        print(
            f"{path.name:24} rows={before_rows:,} land={land:,} "
            f"flagged={flagged} centroid-clusters-excluded={clusters} "
            f"(min_ac={MIN_AC}, coord_cluster>={COORD_CLUSTER})"
        )

    # top-5 sample from the slim file
    slim = json.loads((DOCS / "listings.json").read_text())
    dual = sorted(
        (x for x in slim if x.get("dual")),
        key=lambda z: -(z.get("dual_s") or 0),
    )
    print(f"\ntop-5 by dual_s (of {len(dual)} flagged):")
    print(f"  {'dual_s':>6} {'cf':<14} {'rg':<12} {'$USD':>10} {'ac':>6}  coast/ski km")
    for x in dual[:5]:
        print(
            f"  {x.get('dual_s'):6.1f} {(x.get('cf') or '')[:14]:<14} "
            f"{(x.get('rg') or '')[:12]:<12} {x.get('usd'):10,.0f} "
            f"{x.get('ac'):6.2f}  {x.get('coast_km')}/{x.get('ski_km')}"
        )


if __name__ == "__main__":
    main()
