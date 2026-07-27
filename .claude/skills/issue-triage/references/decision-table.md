# Triage outcomes

Every triaged issue lands in exactly one of A–G. If two seem to fit, prefer the
one that carries more evidence: a duplicate you can also reproduce is still A,
with the duplicate link in the comment. Add `duplicate` to A's labels in that
case — the outcome governs the workflow, the labels describe the issue, and an
issue that is genuinely both should say so.

## One-time label bootstrap

Already in the repo — use as-is, don't recreate or restyle them:
`bug`, `duplicate`, `question`, `enhancement`, `help wanted`.

Create these once, before the first real run:

| Label | Colour | Meaning |
|---|---|---|
| `confirmed` | `b60205` | Reproduced, or traced to specific code |
| `has-repro` | `0e8a16` | A committed test demonstrates it |
| `needs-info` | `fbca04` | Waiting on the reporter; starts the 30-day clock |
| `probably-fixed` | `c2e0c6` | Believed resolved by a named commit |
| `documentation` | `0075ca` | Docs gap rather than a code defect |
| `needs-integration-test` | `5319e7` | Real defect, not expressible in the fakeredis harness |

Check with `get_label` before creating rather than trusting this list — it is a
snapshot, and a triage run that assumes a label exists will fail at the point
where it has already posted the comment.

## A — Confirmed and reproducible

You wrote a test, ran it, and it failed for the reason the reporter described.

1. Branch `claude/triage-issue-NNN` off the default branch.
2. Add `tests/test_issue_NNN.py` per `repro-harness.md`, marked
   `@unittest.expectedFailure`, carrying the `TRIAGE ARTIFACT` docstring note
   that names the permanent home it should move to when fixed.
3. Confirm `python -m unittest tests.test_issue_NNN -v` and `make lint` pass.
4. Open a PR: `test: reproduce #NNN — <symptom>`. The body must say where the
   test should move to at fix time, so the fixer doesn't need this skill.
5. Comment on the issue.

Labels: `bug`, `confirmed`, `has-repro`.

> Confirmed on `main` (`<sha>`). The cause is in
> [`redbeat/schedulers.py:NNN`](link) — `<one sentence, mechanism not symptom>`.
>
> I've added a failing regression test in #PPP:
>
> ```
> <real unittest output>
> ```
>
> It's marked `expectedFailure` so CI stays green; whoever fixes this can drop
> the marker and the test becomes the check. It's a standalone file for now so
> it's easy to find from here — it belongs in `tests/<home>.py` once fixed.

## B — Confirmed, but not expressible as a unit test

You traced it to real code, but the trigger is environmental: a live Redis, a
cluster or sentinel topology, a DST transition, a suspended host, a dropped
connection. A fakeredis test here would pass or fail for the wrong reason, which
is worse than no test.

Labels: `bug`, `confirmed`, `needs-integration-test`. No PR.

> Confirmed by inspection on `main` (`<sha>`): `<file:line trace>`.
>
> I couldn't turn this into a regression test — reproducing it needs
> `<the environmental trigger>`, which the fakeredis-based suite in `tests/`
> can't produce. Flagging it as needing an integration test rather than
> leaving a fake one that would pass for the wrong reason.

## C — Undetermined, needs the reporter

You genuinely could not tell. Say what you tried — that's what separates this
from the "any update?" comments everyone hates — and ask only for what's missing
and not already in the thread.

Label: `needs-info`.

> I tried to reproduce this on `main` (`<sha>`) with `<what you did>`, and
> `<what happened instead>`.
>
> To get further I need:
> - `<specific fact>`
> - `<specific fact>`
>
> If it's no longer affecting you, saying so is just as useful — it lets us
> close this out.

## D — Probably already fixed

Name the commit. "Looks fixed" without one is a C, not a D.

Labels: `probably-fixed`, `needs-info` (the clock should run). Do not close.

> This looks fixed by `<sha>` (`<subject>`), released in `<version>` —
> `<what changed>`. You were on `<their version>`, which predates it.
>
> Could you confirm on `<latest>`? If it still happens I'll dig in properly.

## E — Duplicate

Comment on both: link the canonical issue here, and move any detail this thread
has that the canonical one lacks over there. Then leave both open.

Label: `duplicate`.

> Same root cause as #MMM — `<the shared mechanism>`. That one has the older
> thread, so it's the better place to track it; I've copied the extra detail
> from here across.
>
> Leaving this open for the maintainer to close.

## F — Question or docs gap

Answer it, with links into `docs/`. If the docs don't actually cover it, say so
explicitly — a question that the documentation should have answered is a docs
bug, and naming it is more useful than a private answer.

Label: `question`, or `documentation` when there's a real gap.

> `<direct answer>` — see [`docs/<file>.rst`](link).
>
> (This isn't covered well in the docs today; that's a gap worth closing.)

## G — Enhancement

Not a defect. Summarise what it would take and what today's behaviour is, so the
next reader doesn't restart from the title.

Label: `enhancement`.
