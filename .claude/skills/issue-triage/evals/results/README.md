# Recorded eval runs

One JSON file per comparison run, named `<date>-<what-was-compared>.json`.
These exist so a model change can be checked against a known baseline rather
than a memory of how things used to go.

## What a run record has to pin down

A pass rate is meaningless without the things that produced it, so every record
carries all four:

- `skill_commit` — the skill being measured. A later run against a different
  commit is measuring a different skill.
- `evals_verified_against` — the repo commit the *expectations* were checked at.
  If this differs between two records, some of the delta may be the code moving,
  not the model changing.
- `effort` per run — a model at `low` and the same model at `xhigh` are not
  comparable, and this is the field most easily forgotten.
- `orchestration` — `workflow` runs can set effort per agent; `agent-tool` runs
  inherit the session's. An `agent-tool` record with `"effort": "inherited"` is
  honest; one claiming a specific level is not.

## Comparing two runs

```
python compare.py results/2026-07-27-opus5-sonnet5-haiku45.json \
                  results/<later>.json
```

It reports per-case pass-rate and cost deltas, and refuses to compare records
whose `skill_commit` or `evals_verified_against` differ without saying so loudly
— a silent apples-to-oranges comparison is the main way this kind of file
misleads.

## Reading the numbers honestly

**Pass rate is the weakest signal here.** These assertions were written by hand
against a handful of cases; a model can pass every one and still reach a wrong
verdict, which is exactly what happened on #270 in the first comparison — Sonnet
satisfied the assertion as written while getting the answer wrong, because the
assertion was too loose to tell the two apart. Read the recorded `outcome_reported`
and `notes` alongside the score.

**Cost is not tokens.** Compare dollars, not token counts: a model using more
tokens can still be cheaper. Per-token prices change (Sonnet 5 carries
introductory pricing through 2026-08-31), so `compare.py` reports tokens and
leaves pricing to whoever reads it.

**A case both models pass tells you nothing.** Non-discriminating assertions
should be tightened or dropped, not celebrated.
