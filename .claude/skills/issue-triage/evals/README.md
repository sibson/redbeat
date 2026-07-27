# issue-triage evals

Six cases covering the outcomes that are easy to get wrong, plus the two
behaviours the design depends on: never closing an issue, and never posting a
duplicate comment on a re-run.

## Running them

Ask Claude: **"run the issue-triage evals"**. For each case in `evals.json` it
spawns two subagents in the same turn — one pointed at
`.claude/skills/issue-triage/`, one with no skill as a baseline — saving outputs
under `issue-triage-workspace/iteration-N/<eval-name>/{with_skill,without_skill}/`.
Then it grades each assertion, aggregates, and shows you the comparison.

Every prompt carries `--dry-run`, so the suite investigates real issues but
writes nothing to the repo or to GitHub. That is deliberate: evals that post
comments can only be run once, which makes them not evals.

Verify the dry run held:

```
python .claude/skills/issue-triage/evals/check_no_writes.py \
    issue-triage-workspace/iteration-N/*/*/transcript.jsonl
```

## What each case is for

| Case | Guards against |
|---|---|
| `reproducible-bug-and-duplicate` (#307) | The happy path. Also the only case where a duplicate and a reproduction coexist — #210 is the same defect. |
| `documented-behaviour-not-a-bug` (#218) | Confirming a defect that `docs/design.rst` says is intentional, and writing a test that pins the design in place. |
| `version-obsolescence-check` (#270) | Both failure directions: treating a celery 4.x trace as current, and dismissing a live bug because the report is old. |
| `question-not-a-bug` (#98) | Labelling a usage question as a bug and asking for a traceback that will never exist. |
| `idempotency-on-rerun` (#291) | Re-commenting on an already-triaged issue. |
| `batch-and-overdue-report` | Closing anything, and dropping the overdue section when it's empty. |

## Keeping them honest

These run against the live backlog, so they drift — someone fixes #307 and case 1
should stop reporting outcome A. That drift is informative rather than a bug in
the suite, but the expectations need re-pinning when it happens:

- If an issue gets fixed or closed, either update the expected outcome or swap in
  a comparable open issue and rename the case for what it tests, not the number.
- If a case starts passing for both the with-skill and baseline runs, it has
  stopped discriminating and is no longer earning its slot.
- `notes` in `evals.json` records the date the expectations were pinned. Update
  it when you re-pin.

Case 5 describes prior-triage state in the prompt rather than depending on #291
actually having a triage comment, so it stays valid regardless of backlog state.

A worked example of the above, from the suite's first run: case 2 originally
asserted that #218 was a confirmed-but-untestable defect. The run showed that
`docs/design.rst` documents the behaviour as intentional, so the assertion was
encoding the author's assumption rather than testing the skill — and the skill
had inherited the same wrong assumption as a hardcoded verdict in
`repro-harness.md`. Both were corrected. Expect this: an eval that fails because
your expectation was wrong is the suite paying for itself, so check which of the
two is wrong before "fixing" the skill.
