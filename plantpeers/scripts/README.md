# plantpeers/scripts

## validate_data.py — data-integrity guard (pre-commit / CI)

The plantpeers MVP is a static app whose entire ranking depends on the shape and
internal consistency of `plantpeers/data/*.json`. A bad data edit fails silently
in the browser (blank cards, wrong winner) rather than loudly. This script is the
cheap guard that catches such a regression before it ships.

Run it from the repo root (or anywhere — paths are resolved relative to the
script):

```
python3 plantpeers/scripts/validate_data.py
```

- Pure standard library, no dependencies.
- Exit `0` = all invariants hold (prints a PASS summary with counts).
- Exit non-zero = at least one invariant violated (prints clear `FAIL:` lines).

Wire it in as a pre-commit hook or a CI step on any change under
`plantpeers/data/` (and on `index.html`, since the golden-ranking check mirrors
that file's scoring coefficients — see the header comment in the script).

It asserts: referential integrity, required fields/types/ranges, ledger sanity
(the anti-gaming invariants), id uniqueness, and a golden-ranking check that the
seeded gamer lab (`@tropiflask_wholesale`) ranks LAST and a verified lab ranks #1
for the Florida Beauty request.
