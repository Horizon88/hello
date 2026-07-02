# <PROJECT NAME> — project context

Grounding doc for the venture studio team. Any role working in this project
reads this first. Fill every section; delete the guidance in angle brackets.

## What it is

<One paragraph: what the product is and who it's for.>

## What makes it different

<The core differentiator / insight. What does it do that the obvious competitor
doesn't? This is what the Prototyper protects and the Grower sharpens.>

## The core mechanic (decided)

<The single most important interaction or loop, stated concretely. If a key
product decision has been made, record it here as decided so no role re-litigates
it. This is the thing the whole MVP serves.>

## Data model (MVP)

| Entity | Key fields |
|---|---|
| **<Entity>** | `field`, `field`, … |

## First-loop deliverable

<What the team ships in the first loop — e.g. a clickable MVP prototype, a
concept spike, a landing page. Be specific about the flow/screens/artifacts.>

## Stack / conventions

- <Language/framework. Default here mirrors the studio's proven pattern: a static
  single-page app — plain HTML/CSS/JS, data from JSON, no backend/build step for
  the MVP, runnable via `python -m http.server`.>
- No hard dependency on a third-party CDN that breaks the core flow if it fails —
  inline critical assets, degrade gracefully.
- Idempotent, reviewable: small commits, one concern each.

## Standing user preferences (hard constraints)

- <e.g. Mobile-first.>
- <e.g. Prefers proposals + immediate execution over confirmation loops.>
- <e.g. Do max work autonomously; only ask when it needs account access or a true
  product fork.>

## Open questions (park, don't block the MVP)

- <Things deliberately deferred so the first loop stays focused.>
