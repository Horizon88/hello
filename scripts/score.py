"""Rating function for ocean-view land listings (0-100).

Calibrated for a Canadian citizen. Scores combine value ($/m^2),
country access, view, title security, plot size fit, and practical signals.
"""
from __future__ import annotations
import math, re

ACCESS = {
    "British Columbia": 25,
    "Japan": 23,
    "Malaysia": 18,
    "Thailand": 14,
    "New Zealand": 5,
}

BUMI = re.compile(r"\b(bumi[-\s]?lot|tanah[-\s]?rizab|rizab[-\s]?melayu|malay[-\s]?reserve|reserved[-\s]?malay)\b", re.I)
NON_BUMI = re.compile(r"\b(non[-\s]?bumi)\b", re.I)


def rate(row: dict) -> dict:
    """Mutates row in-place adding 'rating' and 'rating_breakdown'."""
    slug = (row.get("listing_link") or "").lower()
    country = row.get("country", "")

    access = ACCESS.get(country, 10)
    if country == "Malaysia" and BUMI.search(slug) and not NON_BUMI.search(slug):
        access = 0  # foreigner can't buy bumi/Malay-reserved

    try:
        upm2 = float(row["usd_per_m2"])
    except (KeyError, ValueError, TypeError):
        upm2 = 999.0
    value = 25.0 if upm2 <= 0.5 else max(0.0, 25.0 * (1 - math.log10(upm2 / 0.5) / 3))

    view = (row.get("view") or "").lower()
    view_pts = 20 if view == "beachfront" else (15 if view == "sea_visible" else (10 if view == "coastal" else 0))

    title = (row.get("title") or "").lower()
    if "chanote" in title or "freehold" in title:
        title_pts = 15
    elif "title deed" in title:
        title_pts = 10
    elif "nor sor" in title:
        title_pts = 8
    elif "lease" in title:
        title_pts = 5
    else:
        title_pts = 7
    if country == "Malaysia" and BUMI.search(slug):
        title_pts = 0

    try:
        acres = float(row.get("acres") or 0)
    except (ValueError, TypeError):
        acres = 0.0
    if 1 <= acres <= 20:
        size_pts = 10
    elif 20 < acres <= 100:
        size_pts = 7
    elif (0.1 < acres < 1) or (100 < acres <= 300):
        size_pts = 4
    else:
        size_pts = 2

    prac = 0
    try:
        if float(row.get("elev_m") or 0) > 20:
            prac += 3
    except (ValueError, TypeError):
        pass
    if any(k in slug for k in ("panoram", "sea-view", "sea_view", "ocean", "view")):
        prac += 2
    prac = min(prac, 5)

    rating = round(access + value + view_pts + title_pts + size_pts + prac, 1)
    row["rating"] = rating
    row["rating_breakdown"] = (
        f"acc{access}+val{value:.0f}+view{view_pts}+title{title_pts}+size{size_pts}+prac{prac}"
    )
    return row
