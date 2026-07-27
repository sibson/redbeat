# Writing a redbeat regression test

The suite has a few conventions that differ from what you'd write by instinct.
Getting them wrong produces a test that silently never runs, which is the worst
possible outcome for a regression test.

## The conventions that will catch you out

**stdlib `unittest`, not pytest.** `setup.cfg` has a vestigial `[tool:pytest]`
stub, but pytest isn't installed and isn't used. Runner is
`python -m unittest discover tests`. Use `self.assertEqual` and friends, not bare
`assert`.

**Override `setup()`, not `setUp()`.** `AppCase.setUp` builds the celery test app
and then calls `self.setup()`. Define `setUp` instead of `setup` and you silently
skip app construction; call `setup` without chaining `super().setup()` and you
lose the fakeredis wiring.

**Classes are named `test_Thing`** — lowercase `test_` prefix, an old celery
convention that the rest of the suite follows (`test_RedBeatEntry`,
`test_RedBeatScheduler_schedule`). A `TestThing` class won't be collected.

**No registration, no Redis.** Drop the file in `tests/`, discovery finds it.
`RedBeatCase` hands you `self.app` and a `fakeredis`-backed
`self.app.redbeat_redis`, flushed per test.

## Shape

```python
import unittest
from datetime import datetime, timezone

from celery.schedules import crontab

from tests.basecase import RedBeatCase


class test_Issue_307(RedBeatCase):
    """due_at adds remaining_estimate to last_run_at instead of now.

    https://github.com/sibson/redbeat/issues/307

    Expected: the next 06:00 UTC occurrence after now.
    Actual:   last_run_at + (time from now until that occurrence).

    TRIAGE ARTIFACT -- this file is temporary. When the fix lands, move this
    test into tests/test_entry.py::test_RedBeatEntry, drop the
    expectedFailure marker, rename it for the behaviour it checks rather
    than the issue number, and delete this file.
    """

    @unittest.expectedFailure
    def test_due_at_uses_now_not_last_run_at(self):
        now = datetime(2026, 1, 21, 21, 32, tzinfo=timezone.utc)
        entry = self.create_entry(
            s=crontab(hour=6, minute=0, nowfun=lambda: now),
            last_run_at=datetime(2026, 1, 21, 6, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(
            entry.due_at, datetime(2026, 1, 22, 6, 0, tzinfo=timezone.utc)
        )
```

`self.create_entry(name=, task=, s=, run_every=, **kwargs)` builds a
`RedBeatSchedulerEntry`; extra kwargs pass straight through, so `last_run_at`,
`args`, `kwargs` and `options` all work.

## Why `expectedFailure`

The test lands before the fix, so it has to fail. `expectedFailure` keeps CI
green while committing the reproduction, and — the useful part — `unittest`
reports an *unexpected success* as a failure. The day someone fixes the bug, the
suite tells them this test is now passing and the marker should come off. It's a
regression test that also announces its own resolution.

Put the issue URL and an explicit expected-vs-actual in the docstring. Six months
from now that docstring is the only context anyone has.

## What is and isn't testable here

Judge each issue on its own; don't take a verdict from a list. The question is
narrower than "can I simulate the user's situation" — it is **can I put the code
into the state where the defect occurs**. Those come apart more often than you'd
expect, and mistaking the first for the second is the main way this step goes
wrong in both directions.

Usually testable, because the trigger is arithmetic and the clock is injectable
via `nowfun`: `due_at` and `remaining_estimate` errors, first-run timing after
`save()` with `last_run_at` unset, rrule start handling, JSON round-tripping in
`redbeat/decoder.py`.

Often testable even when the *cause* isn't reproducible, because the state the
cause produces is reachable directly through `self.app.redbeat_redis`. A key
evicted by Redis and a key you deleted are indistinguishable to the client, so
"entry vanished from the ZSET" or "the lock is gone" are reachable states even
though eviction and host suspend are not reachable events. If the defect is what
the code does *on discovering* that state, you can test it.

Genuinely out of reach — outcome B — is behaviour that depends on machinery
fakeredis doesn't model: cluster key-slot routing, sentinel failover, connection
loss and retry. Here you would have to mock the very thing that's broken, and the
test would pass or fail for reasons unrelated to the bug.

Before writing any of it, check the behaviour isn't intended. `docs/design.rst`
documents deliberate choices that look like defects from the outside — beat
exiting when it loses the lock is the notable one. A test asserting documented
behaviour pins the design in place while claiming to be a bug report.

## Where the test lives, and where it goes

A per-issue file is the right shape for triage and the wrong shape for the
codebase. It buys something real while the issue is open — one file, obviously
disposable, named so anyone can connect it to the thread — but a `tests/`
directory that accumulates `test_issue_74.py`, `test_issue_154.py`,
`test_issue_307.py` is a tree of orphans nobody dares delete, organised by the
one fact that stops mattering the moment the bug is fixed.

So the file is explicitly a staging area, and the fix is what retires it. Pick
its permanent home when you write it, and say so in three places, because the
person who fixes this may never read this skill:

- the class docstring (the `TRIAGE ARTIFACT` note above),
- the PR body,
- the triage comment on the issue.

Homes, by what the test touches:

| Subject | Home |
|---|---|
| `RedBeatSchedulerEntry` — `due_at`, `score`, `save`, `reschedule` | `tests/test_entry.py` |
| `RedBeatScheduler` — ticks, locking, schedule loading | `tests/test_scheduler.py` |
| JSON encode/decode round-trips | `tests/test_json.py` |
| `rrule` and schedule types | `tests/test_schedules.py` |
| `RedBeatConfig` and settings | `tests/test_config.py` |

If nothing fits, that is worth saying in the PR rather than defaulting to a new
file — it usually means the test is aimed at something the suite doesn't cover
yet, which is useful information about the suite.

## Known harness limits

`fakeredis` ships without Lua support, so anything routed through `EVALSHA`
fails with `ResponseError: unknown command 'evalsha'`. Redis lock operations use
a CAS-on-token Lua script, so `lock.extend()` and `lock.release()` hit this:

```
>>> r.lock('k', timeout=30).extend(30)
ResponseError: unknown command 'evalsha', ...
```

This is a missing dev dependency, not a fact about the bug — reading it as
"unreproducible" would be wrong. `fakeredis[lua]` (which pulls in `lupa`) makes
these work. `requirements-dev.txt` currently pins plain `fakeredis>=2.27.0`, so a
PR containing a lock-related test needs to bump that in the same change, or CI
will fail on an error that has nothing to do with the test.

## Before opening the PR

```
python -m unittest tests.test_issue_NNN -v   # must report expected failure
make lint                                    # flake8 + black + isort
```

Lint is enforced in CI: line length 100, single quotes
(`skip-string-normalization`), isort `profile = hug`.
