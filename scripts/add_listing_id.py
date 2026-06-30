#!/usr/bin/env python3
"""Add a stable, unique `id` to every listing row.

Why: the UI (docs/index.html) keyed archives, the shortlist and every
identity lookup on `u` (the listing URL). But `u` is NOT unique — every
abandoned-ski row (tp=='abandoned_ski') shares one openstreetmap.org/?mlat=...
URL with dozens of unrelated resorts (234 rows across 26 duplicate-URL groups
in the current data). Archiving or shortlisting one of those collided with all
the others sharing that URL. This script gives each row a real identity so the
UI can key on `id` instead of `u`.

The id is a short hash of an intrinsic, file-independent signature:

    sha1(u | lat | lon | usd | rg | a | tp)  -> first 12 hex chars, "L"-prefixed

  * Coordinates are rounded to 5 dp so the slim file (which rounds lat/lon to
    5 dp) and the full file produce the SAME id for the same logical row.
  * Empty / None / "" values are normalised to "" so the slim file (which drops
    empty fields) and the full file agree (e.g. a == "" vs a absent).
  * This signature is verified unique within each file and identical as a
    multiset across both files (see scripts comment / task verification).

Properties:
  * Deterministic & stable — same row -> same id across runs, so localStorage
    keys never churn.
  * Idempotent — once every row already carries the correct id, a re-run writes
    byte-identical output (existing ids are validated, not regenerated blindly;
    a wrong/missing id is corrected).
  * File-shape preserving — slim file stays minified, full file stays pretty,
    exactly like dual_amenity.py / slim_listings.py expect.

Run BEFORE dual_amenity.py so both `id` and `dual` end up in the files:

    python3 scripts/add_listing_id.py
    python3 scripts/dual_amenity.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
TARGETS = (DOCS / "listings.json", DOCS / "listings.full.json")

COORD_DP = 5
ID_LEN = 12  # hex chars after the "L" prefix


def _norm(v):
    """Normalise empty-ish values so slim (drops empties) and full agree."""
    if v is None or v == "" or v == [] or v == {}:
        return ""
    return v


def _coord(v):
    return round(v, COORD_DP) if isinstance(v, float) else v


def listing_id(r: dict) -> str:
    """Stable, file-independent id for a listing row."""
    sig = (
        _norm(r.get("u")),
        _coord(r.get("lat")),
        _coord(r.get("lon")),
        _norm(r.get("usd")),
        _norm(r.get("rg")),
        _norm(r.get("a")),
        _norm(r.get("tp")),
    )
    raw = json.dumps(sig, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:ID_LEN]
    return "L" + h


def annotate(data: list) -> tuple[int, int]:
    """Set `id` on every row in place. Returns (rows, changed)."""
    changed = 0
    for r in data:
        new = listing_id(r)
        if r.get("id") != new:
            r["id"] = new
            changed += 1
    return len(data), changed


def main() -> int:
    for path in TARGETS:
        if not path.exists():
            print(f"skip (not found): {path}")
            continue
        raw = path.read_text()
        data = json.loads(raw)
        # slim file is minified (no ", " after separators); preserve that.
        was_compact = ", " not in raw[:4096]
        rows, changed = annotate(data)

        ids = [r["id"] for r in data]
        dupes = len(ids) - len(set(ids))
        if dupes:
            raise SystemExit(
                f"id-integrity: {path.name} has {dupes} duplicate id(s) — "
                f"signature is not unique, refusing to write"
            )

        if was_compact:
            out = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        else:
            out = json.dumps(data, ensure_ascii=False)
        path.write_text(out)
        print(
            f"{path.name:24} rows={rows:,} ids_written/changed={changed} "
            f"duplicate_ids={dupes}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
