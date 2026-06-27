# regwatch

Weekly watchdog that monitors **official** regulation pages and opens a GitHub
issue whenever one of them changes. No model, no scraping heuristics — it
fetches each page, normalises it to stable text, and diffs it against the last
snapshot stored in git.

> Self-contained subproject: everything lives under `regwatch/`, except the
> workflow, which sits at the repo root (`.github/workflows/check-regulations.yml`)
> because GitHub only runs workflows from there.

## What it watches

| Area | Official sources |
|---|---|
| **Canada passport** | canada.ca passport fees, fee-change notice, adult renewal + renewal eligibility |
| **Canada citizenship (Bill C-3)** | LEGISinfo official bill record + IRCC implementation page (citizenship by descent) |
| **Thailand LTR visa** | BOI LTR portal home, required documents, laws & regulations |
| **BVI companies** | BVI FSC fees, beneficial ownership, industry updates |
| **Grenada passport (CBI)** | Grenada Citizenship by Investment official site |

The full, editable list lives in [`sources.json`](sources.json) — add or remove
URLs there (each needs a unique `id`). An optional per-source `strip` list of
regexes lets you suppress noisy parts of a specific page.

## How it works

1. **`scripts/check.py`** fetches every source, strips scripts/styles and
   volatile bits (timestamps, "date modified" footers, build hashes, CSRF
   nonces…), reduces the page to line-oriented text, and hashes it. It writes:
   - `data/snapshots/<id>.txt` — latest text per source (git keeps the history,
     so every change is a reviewable git diff).
   - `data/state.json` — per-source hash, status, last-checked / last-changed.
   - `data/changes.json` — only the sources that changed this run.
   - `data/STATUS.md` — at-a-glance table.
2. **`scripts/notify.py`** opens one GitHub issue per changed source, including
   the diff of the page text. Labels: `regulation-change` + the area label
   (e.g. `canada-passport`). You get email notifications for new issues.
3. The **workflow** commits the refreshed `data/` back to the branch.

A transient network/HTTP error is recorded as a `status: error` in
`data/state.json` but is **not** treated as a change — it never raises a false
alert just because a site was briefly unreachable.

## Schedule

Runs every **Monday 08:00 UTC**. Trigger manually via the **Actions** tab →
*Check regulations* → *Run workflow*.

> **Note:** GitHub's `schedule` trigger only fires on the repository's **default
> branch**. Merge this branch into the default branch (or make it the default)
> for the weekly cron to run. `workflow_dispatch` works from any branch.

## Local run

```bash
python regwatch/scripts/check.py
cat regwatch/data/STATUS.md
cat regwatch/data/changes.json
```

`notify.py` is a no-op locally (it needs `GITHUB_TOKEN` + `GITHUB_REPOSITORY`,
which the workflow supplies).

## Caveats

- The first run records a **baseline** for every source (no alerts). Real change
  detection starts from the second run.
- JS-rendered pages: the checker sees the server-delivered HTML only. If a site
  renders its content entirely client-side, changes inside that content may not
  be detected — verify those manually or point `sources.json` at an underlying
  data/API URL.
- The diff in each issue is a **signal, not legal advice**. Always confirm
  against the live official page before acting on any regulatory change.
