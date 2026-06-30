#!/usr/bin/env python3
"""Slim docs/listings.json down to only the fields the UI actually reads.

The UI (docs/index.html) lazy-loads docs/listings.json on first paint. That
file carries ~70 keys per listing, but the front-end only ever reads ~49 of
them. The rest (mls, name, foreign_note, zoning, desc, beds/baths, scoring
sub-bonuses, geocode debris, ...) are pure page-weight: never rendered, never
filtered, never sorted.

This script is a behavior-preserving build step:

  * Keep exactly the keys the UI references off a listing object.
  * Drop null / empty values — the UI tests every optional field with
    `!= null` or a truthy check, and `sortRows` treats null and missing
    identically, so an absent key renders the same as a null one.
  * Round lat/lon to 5 decimal places (~1.1 m). The map never zooms past
    level 11, where that is far finer than a pixel.

The full, unslimmed export is preserved as docs/listings.full.json so the
canonical rich data is never lost (pipeline / future fields can read it).

Run:  python scripts/slim_listings.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
SRC = DOCS / "listings.json"
FULL_BACKUP = DOCS / "listings.full.json"

# Exactly the keys docs/index.html reads off a listing object `r`.
# Verified by grepping `r.<field>` in index.html (see task changelog).
KEEP = (
    # core / always-present
    "cf", "r", "rg", "a", "ac", "m2", "usd", "upm", "v", "el", "t",
    "lat", "lon", "cur", "lp", "rb", "img", "imgs", "u", "apt", "apt_km",
    "tp", "foreign_friction", "coast_km", "ski_km", "ski_r",
    # optional flags / detail-popover fields
    "view_verified", "floor", "pool", "distressed",
    "pid", "plan", "owner_type", "official_m2", "official_acres",
    "year_closed", "closure_status", "geocode_src", "wiki_jp",
    "distress", "distress_breakdown", "size_mismatch",
    "fullfloor", "duplex", "terrace_km", "terrace_bonus", "terrace_zone",
    "npa", "structural_warn",
)

COORD_KEYS = ("lat", "lon")
COORD_DP = 5


def slim_row(r: dict) -> dict:
    out = {}
    for k in KEEP:
        if k not in r:
            continue
        v = r[k]
        if v is None:
            continue
        # drop empty containers/strings — the UI treats them as absent
        if v == "" or v == [] or v == {}:
            continue
        if k in COORD_KEYS and isinstance(v, float):
            v = round(v, COORD_DP)
        out[k] = v
    return out


def main() -> int:
    if not SRC.exists():
        print(f"error: {SRC} not found", file=sys.stderr)
        return 1

    raw = SRC.read_text()
    data = json.loads(raw)
    before = len(raw.encode())

    # Preserve the canonical full export once (don't clobber an existing
    # backup with already-slimmed data on a re-run).
    if not FULL_BACKUP.exists():
        FULL_BACKUP.write_text(raw)

    slim = [slim_row(r) for r in data]
    out = json.dumps(slim, separators=(",", ":"), ensure_ascii=False)
    SRC.write_text(out)
    after = len(out.encode())

    print(f"listings:      {len(data):,} -> {len(slim):,}")
    print(f"bytes:         {before:,} -> {after:,}")
    print(f"reduction:     {before - after:,} bytes ({(before - after) / before * 100:.1f}%)")
    print(f"full backup:   {FULL_BACKUP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
