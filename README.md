# Coastal land weekly scanner

Weekly GitHub Actions workflow that scrapes ocean-view land listings from five
markets, scores each on a 0–100 rubric, and opens a GitHub issue when a *new*
listing rates **≥90**.

## Markets covered

| Country | Source | Notes |
|---|---|---|
| Thailand | FazWaz sea-view land | Krabi / Phuket / Phang Nga / Trang |
| New Zealand | realestate.co.nz JSON:API | rural_sale + res_sale, raw land (floor-area = 0) |
| British Columbia | REW land-lot | Vancouver Island / Sunshine Coast / Powell River |
| Malaysia | Mudah `lands+for+sale` | Coastal states; cars filtered; bumi/Malay-Reserved flag in scoring |
| Japan | SUUMO `/tochi/` | Boso / Izu / Hayama / Wakayama / Okinawa / Niigata / Kyushu / Hokkaido coasts |

## Scoring (0–100)

See `scripts/score.py`. Components:
- **Country access** for a Canadian citizen (0–25): BC 25, Japan 23, Malaysia 18, Thailand 14, NZ 5
- **Value** ($/m², log scale, 0–25): aggressively rewards cheap
- **View** (0–20): beachfront 20, sea-visible 15, coastal 10
- **Title security** (0–15): Freehold/Chanote 15, Title Deed 10, Nor Sor 3 8, Lease 5, bumi/Malay-reserved 0
- **Size band fit** (0–10): 1–20 ac peak, then 20–100 ac, then small/very-large
- **Practical** (0–5): elevation bonus, view keyword bonus

≥ **80** = strong combo (cheap + view + clean title + accessible) → triggers a "do further due diligence" GitHub issue.

Override the threshold via the `DD_THRESHOLD` env var on the workflow if you want it stricter or looser.

## Cron

Runs every Monday at 09:00 UTC. Trigger manually via the **Actions** tab → *Weekly land scan* → *Run workflow*.

## What the workflow does

1. `scripts/scan.py` scrapes the five sources, rates everything, writes:
   - `data/latest.csv` — all listings this run (sorted by rating desc)
   - `data/new_high.json` — newly-seen listings with rating ≥ 80 (DD candidates)
   - `data/seen.json` — running set of listing URLs already processed
2. `scripts/notify.py` opens a GitHub issue per new high-rated listing
   (labels: `land-alert`, `rating-NN`). You get email notifications for new issues.
3. The workflow commits updated `data/` back to the branch.

## Local run

```bash
python scripts/scan.py
cat data/new_high.json
```

## Archive-aware scoring (user feedback loop)

The app (`docs/index.html`) lets you **archive** any listing with quick-tags
("no view", "too remote", "ferry required", "bumi/Malay-reserved", …) and a
free-text reason. Archives are persisted in browser localStorage; use
**⬇ export archives** to download `archives.json`.

Commit that file to `data/archives.json` and the next cron run will:
- **Drop the rating to 0** for any URL you've explicitly archived.
- **Penalise the region** (country + region pair) by up to 20 points when
  ≥2 listings there are archived with the same tag — so the same patterns
  stop triggering DD alerts.

This is the cheap-but-effective version of "the AI learns why this property
wasn't right" — no model, just deterministic pattern matching from your
revealed preferences.

## Caveats

- Bare-earth coastal filter only; the rigorous LOS ocean-view test is omitted
  here for runtime/reliability. Source filters already restrict to coastal/sea-view.
- Malaysia data needs per-title verification for **Tanah Rizab Melayu** —
  the scorer drops `access`/`title` to 0 when the listing slug explicitly says
  "bumi-lot" / "Malay-reserved", but unmarked listings still need a manual check.
- New Zealand listings without an asking price (`Deadline Sale` / `Tender`) are
  excluded — they cannot be marked-to-market.
- All FX rates are stamped in `scripts/scan.py` (`NZD 0.60`, `CAD 0.73`,
  `MYR 0.21`, `JPY 0.0064`); update if needed.
