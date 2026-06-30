#!/usr/bin/env python3
"""Shared dual-amenity scoring primitives.

The "dual-amenity" lens surfaces the rare land parcels that are BOTH coastal AND
ski-accessible, and cheap — the product's namesake combination that the live
size-dominant rating `r` buries. The score is geometric (both-required): a parcel
with only one of the two amenities scores 0, because a sum can fake co-occurrence
but a product cannot.

These four functions are the single source of truth for that math, imported by
both the production post-processor (scripts/dual_amenity.py) and the ranking-
comparison harness (experiments/dual_amenity_score.py).
"""
import math


def sea_strength(x):
    """0..1 how strongly this reads as an ocean parcel."""
    if x.get("view_verified") is True:
        base = 1.0
    elif x.get("v") in ("beachfront", "sea_visible", "coastal"):
        base = 0.7
    else:
        base = 0.0
    ck = x.get("coast_km")
    if isinstance(ck, (int, float)):
        # closer water = stronger; full credit <1km, fades to 0 by 10km
        base = max(base, max(0.0, 1.0 - ck / 10.0))
    return base


def ski_strength(x):
    """0..1 how ski-accessible this parcel is."""
    k = x.get("ski_km")
    if not isinstance(k, (int, float)):
        return 0.0
    # ski-in (<1km)=1.0, fades to 0 by 12km
    return max(0.0, 1.0 - k / 12.0)


def cheapness(x):
    """0..1; cheap parcels score high. Absolute USD, not $/m2 — the user wants a
    parcel they can actually buy, so a $6k lot beats a $2M one regardless of size."""
    usd = x.get("usd")
    if not isinstance(usd, (int, float)) or usd <= 0:
        return 0.0
    # log scale: $5k -> ~1.0, $50k -> ~0.7, $500k -> ~0.4, $5M -> ~0.1
    return max(0.0, min(1.0, 1.0 - (math.log10(usd) - 3.7) / 3.3))


def dual_score(x):
    """Geometric both-required score 0..100; 0 unless BOTH amenities are present."""
    s, k, c = sea_strength(x), ski_strength(x), cheapness(x)
    combo = math.sqrt(s * k)  # 0 unless BOTH present
    return round(100 * combo * (0.5 + 0.5 * c), 1)
