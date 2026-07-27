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

Testable, because the trigger is arithmetic and you can inject the clock via
`nowfun`:

- `due_at` / `remaining_estimate` errors (#210, #307)
- first-run timing after `save()` when `last_run_at` is unset (#154)
- rrule start-time handling (#74)
- JSON round-tripping of schedules and metadata (`redbeat/decoder.py`)
- entry disappearing when its hash is gone but the ZSET member remains (#291) —
  deletable directly through `self.app.redbeat_redis`

Not testable in this harness — these are outcome B:

- lock loss from a suspended host or clock jump (#218), re-election after a DST
  transition (#306)
- cluster key-slot behaviour (#296), sentinel failover (#156)
- server-closed connections and retry behaviour (#252, #285) — fakeredis doesn't
  model connection loss faithfully enough for the test to mean anything

The line is whether fakeredis reproduces the *mechanism* or merely the *shape* of
the failure. If you'd have to mock the thing that's actually broken, the test
proves nothing.

## Before opening the PR

```
python -m unittest tests.test_issue_NNN -v   # must report expected failure
make lint                                    # flake8 + black + isort
```

Lint is enforced in CI: line length 100, single quotes
(`skip-string-normalization`), isort `profile = hug`.
