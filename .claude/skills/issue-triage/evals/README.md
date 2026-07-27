# issue-triage evals

Six cases covering the outcomes that are easy to get wrong, plus the two
behaviours the design depends on: never closing an issue, and never posting a
duplicate comment on a re-run.

## Why these read fixtures, not the live API

An eval pointed at a live issue decays in two directions, and neither failure is
loud.

The backlog moves. Someone fixes `due_at` and case 1's "confirmed and
reproducible" expectation is now wrong — the run that correctly reports
"already fixed" fails an assertion, and the suite reports a regression that
isn't one.

Worse, this skill *writes to the threads its own evals read*. The first real
triage run on #291 puts a full analysis in the thread; every later eval run then
scores well by reading back an answer a previous run posted. That's a suite that
looks healthy while measuring nothing.

So each case reads a frozen snapshot of the issue as originally filed —
`fixtures/issue-<N>.json`, built by `snapshot.py`. Comments after the pin date
are withheld, and `state` / `state_reason` / `labels` are stripped so a closed
issue can't announce its own verdict.

Batch mode reads a frozen backlog the same way, from `fixtures/backlog.json`.
Which issues it picks and what it calls overdue are judgments, and both change
as the real backlog is worked — so they need pinning too, or the case measures
the state of the repo rather than the quality of the selection.

## Get the repo into the state the skill assumes, first

Fixtures freeze the issue, not the repo the skill acts on. The first comparison
run was built before the labels the outcomes depend on existed, so two case 1
runs spent effort discovering — correctly, and identically — that a live run
would propose labels it could not apply. That's a real finding about the repo,
but it isn't what the case was measuring, and it would have recurred on every
run until someone fixed it.

Anything the skill treats as a precondition — labels, branch protection, the
dev dependencies a proposed test would need — should be true before a run is
recorded. Otherwise the suite spends its budget rediscovering setup gaps and
the notes fill up with findings that say more about the repo than the model.

## What a fixture does and doesn't freeze

It freezes the **input**: the issue as the reporter filed it. It does not freeze
the **code**, and it shouldn't. If someone fixes the `due_at` bug, the correct
triage outcome for #307 genuinely changes from "confirmed" to "already fixed",
and an eval that still demanded "confirmed" would be wrong rather than strict.

That drift is legitimate, so the goal is to *detect* it rather than prevent it.
`verified_against` in `evals.json` records the commit the expectations were last
checked against. When HEAD has moved well past it and a case starts failing,
check whether the code changed under the expectation before treating it as a
skill regression — those are opposite problems with opposite fixes.

These cases measure one thing: whether the skill reaches good triage judgments.
They are not a functional or integration test, and shouldn't grow into one —
if the API tools break you find out the moment you run the skill, and an
assertion about them here would only add a way for the suite to go red for
reasons that have nothing to do with triage quality.

## Running them

Ask Claude: **"run the issue-triage evals"**. For each case it spawns two
subagents in the same turn — one pointed at `.claude/skills/issue-triage/`, one
with no skill as a baseline — saving outputs under
`issue-triage-workspace/iteration-N/<eval-name>/{with_skill,without_skill}/`.
Then it grades each assertion, aggregates, and shows the comparison.

Every prompt carries `--dry-run`, so the suite investigates real code but writes
nothing. Verify that held:

```
python .claude/skills/issue-triage/evals/check_no_writes.py \
    issue-triage-workspace/iteration-N/*/*/transcript.jsonl
```

## Adding a case

```
# Claude fetches the issue and pipes it in; MCP tools aren't reachable from a script.
python snapshot.py --number 319 --as-of 2026-07-21 < fetched.json
```

Pin `--as-of` to the day the issue was filed, so the fixture is the report rather
than the discussion that followed.

**Closed issues make the strongest cases**, because the resolution is knowable —
but only those closed `completed`. Roughly 25 of this repo's closed issues were
swept in a single bulk pass on 2025-02-24 and carry `not_planned`; that records a
disposition, not a verdict, and grading against it would teach the skill that old
means closeable. `snapshot.py` strips `state_reason` from the fixture either way,
so the distinction has to be made when choosing the case, not at grading time.

## What each case is for

| Case | Guards against |
|---|---|
| `reproducible-bug-and-duplicate` (#307) | The happy path. Also the only case where a duplicate and a reproduction coexist — #210 is the same defect. |
| `documented-behaviour-not-a-bug` (#218) | Confirming a defect that `docs/design.rst` says is intentional — and the opposite error of closing the whole report because the headline behaviour is documented. |
| `version-obsolescence-check` (#270) | Both failure directions: treating a celery 4.x trace as current, and dismissing a live bug because the report is old. |
| `question-not-a-bug` (#98) | Labelling a usage question as a bug and asking for a traceback that will never exist. |
| `idempotency-on-rerun` (#291) | Re-commenting on an already-triaged issue. |
| `batch-and-overdue-report` | Closing anything, and an overdue check that only finds issues the process already touched. |

Case 5 uses `fixtures/synthetic-291-prior-triage.json` — a hand-written thread
ending in a triage comment, not a snapshot. It has to be synthetic: the whole
point is a state no real thread was in yet. The first version of this case simply
*asserted* in the prompt that a prior comment existed; the run checked the real
thread, found the newest comment was the reporter's, and flagged the
contradiction instead of playing along. Right call, and it left the case unable
to test the thing it was named for. An eval that describes a world the agent can
check has to be right about that world, or it only measures credulity.

## Keeping them honest

- If a case starts passing for both the with-skill and baseline runs, it has
  stopped discriminating and is no longer earning its slot.
- An assertion loose enough that two contradictory answers both satisfy it is
  worse than no assertion. Case 3 once read "lands in outcome C or D" and passed
  two runs that disagreed about whether the bug was fixed.
- When a case fails, decide which is wrong — the skill or the expectation —
  before editing either.
