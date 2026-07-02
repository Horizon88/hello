# Venture studio scaffold

A drop-in bundle to stand up the venture studio — the reusable five-role team
plus a project starter — in a fresh repo (e.g. `venture-studio`), and to stamp
out new ventures inside it with one command.

## What's in here

```
scaffold/
├─ .claude/agents/         the five reusable roles + README (prototyper, builder,
│                          sweeper, grower, maintainer) — project-agnostic; each
│                          grounds itself on a project's CONTEXT.md
├─ CONTEXT.template.md      per-project grounding doc to fill in
├─ project-skeleton/        minimal mobile-first static app (index.html + data/)
│                          — no CDN deps, loads JSON, degrades gracefully
└─ new-project.sh           stamp out a new project directory from the above
```

## Set up the studio in a new repo (one time)

From a Claude Code session **scoped to the target repo** (or locally):

```bash
# in the root of the new repo (e.g. venture-studio):
cp -r /path/to/scaffold/.claude .          # install the reusable team
cp -r /path/to/scaffold .                  # keep the scaffold for stamping projects
git add .claude scaffold && git commit -m "Install venture studio team + scaffold"
```

If you're copying from this bundle's tarball, extract it at the repo root and run
the same `git add`/`commit`.

## Start a new venture

```bash
scaffold/new-project.sh <slug> "<Project Name>"
# e.g.
scaffold/new-project.sh plantpeers "plantpeers.com"
```

This creates `<slug>/` with `CONTEXT.md` (from the template) and the static-app
skeleton. Then:

1. Fill in `<slug>/CONTEXT.md` — product, the core mechanic (record decisions as
   *decided* so no role re-litigates them), data model, first-loop deliverable,
   and standing user preferences (treated as hard constraints).
2. Point the team at it. The agents read the nearest `CONTEXT.md` to ground
   themselves; kick off the loop with the **Prototyper**, then **Builder**, then
   **Sweeper / Grower / Maintainer**.
3. Run it: `(cd <slug> && python -m http.server 8000)` and open `index.html`.

## The loop

Prototyper (many cheap ideas) → Builder (ship the one with signal) →
Sweeper (simplify/unship) + Grower (tune for PMF) → Maintainer (keep it reliable
at scale). See `.claude/agents/README.md` for the full handoff graph and when to
reach for each role.
