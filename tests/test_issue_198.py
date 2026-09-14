import unittest

from redbeat.schedulers import RedBeatScheduler, get_redis
from tests.basecase import RedBeatCase


class test_Issue_198(RedBeatCase):
    """setup_schedule() runs before the distributed lock is acquired.

    https://github.com/sibson/redbeat/issues/198

    RedBeatScheduler.__init__ calls setup_schedule() (via the base
    Scheduler.__init__, non-lazy) before `beat_init` ever fires, so
    `self.lock` is still None the first time setup_schedule() writes the
    static entries. A second instance started with a different
    beat_schedule -- e.g. during a rolling release -- overwrites the
    statics set the lock-holding instance is actually running, and does
    so whether or not it goes on to win the lock.

    Expected: an instance that does not hold the lock leaves an
    existing static schedule alone.
    Actual:   it rewrites the statics set from its own beat_schedule
              regardless of lock state.

    TRIAGE ARTIFACT -- this file is temporary. When the fix lands, move
    this test into tests/test_scheduler.py, drop the expectedFailure
    marker, rename it for the behaviour it checks rather than the issue
    number, and delete this file.
    """

    @unittest.expectedFailure
    def test_setup_schedule_without_lock_leaves_schedule_alone(self):
        self.app.conf.beat_schedule = {'task-old': {'task': 'tasks.old', 'schedule': 60}}
        winner = RedBeatScheduler(app=self.app, lazy=False)
        winner.lock = object()  # simulate having acquired the distributed lock

        client = get_redis(self.app)
        self.assertEqual(client.smembers(self.app.redbeat_conf.statics_key), {'task-old'})

        self.app.conf.beat_schedule = {'task-new': {'task': 'tasks.new', 'schedule': 60}}
        loser = RedBeatScheduler(app=self.app, lazy=False)
        self.assertIsNone(loser.lock)

        self.assertEqual(client.smembers(self.app.redbeat_conf.statics_key), {'task-old'})
