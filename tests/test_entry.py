import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from celery.schedules import schedule
from celery.utils.time import maybe_make_aware

from redbeat import RedBeatSchedulerEntry
from redbeat.decoder import RedBeatJSONDecoder, from_timestamp, to_timestamp
from tests.basecase import RedBeatCase

CELERY_CONFIG_DEFAULT_KWARGS = {}


class test_RedBeatEntry(RedBeatCase):
    def test_basic_save(self):
        e = self.create_entry()
        e.save()

        expected = {
            'name': 'test',
            'task': 'tasks.test',
            'schedule': e.schedule,
            'args': None,
            'kwargs': CELERY_CONFIG_DEFAULT_KWARGS,
            'options': {},
            'enabled': True,
        }
        expected_key = self.app.redbeat_conf.key_prefix + 'test'

        redis = self.app.redbeat_redis
        value = redis.hget(expected_key, 'definition')
        self.assertEqual(expected, json.loads(value, cls=RedBeatJSONDecoder))
        self.assertEqual(redis.zrank(self.app.redbeat_conf.schedule_key, e.key), 0)
        self.assertEqual(redis.zscore(self.app.redbeat_conf.schedule_key, e.key), e.score)

    def test_from_key_nonexistent_key(self):
        with self.assertRaises(KeyError):
            RedBeatSchedulerEntry.from_key('doesntexist', self.app)

    def test_from_key_missing_meta(self):
        initial = self.create_entry().save()

        loaded = RedBeatSchedulerEntry.from_key(initial.key, self.app)
        self.assertEqual(initial.task, loaded.task)
        self.assertIsNotNone(loaded.last_run_at)

    def test_next(self):
        initial = self.create_entry().save()
        now = self.app.now()
        # 3.x is naive but 4.x is aware
        now = maybe_make_aware(now)

        n = initial.next(last_run_at=now)

        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(n.last_run_at, now)
        self.assertEqual(initial.total_run_count + 1, n.total_run_count)

        # updated meta was stored into redis
        loaded = RedBeatSchedulerEntry.from_key(initial.key, app=self.app)
        self.assertEqual(loaded.last_run_at, now)
        self.assertEqual(loaded.total_run_count, initial.total_run_count + 1)

        # new entry updated the schedule
        redis = self.app.redbeat_redis
        self.assertEqual(redis.zscore(self.app.redbeat_conf.schedule_key, n.key), n.score)

    def test_next_only_update_last_run_at(self):
        initial = self.create_entry()

        n = initial.next(only_update_last_run_at=True)
        self.assertGreater(n.last_run_at, initial.last_run_at)
        self.assertEqual(n.total_run_count, initial.total_run_count)

    def test_delete(self):
        initial = self.create_entry()
        initial.save()

        e = RedBeatSchedulerEntry.from_key(initial.key, app=self.app)
        e.delete()

        exists = self.app.redbeat_redis.exists(initial.key)
        self.assertFalse(exists)

        score = self.app.redbeat_redis.zrank(self.app.redbeat_conf.schedule_key, initial.key)
        self.assertIsNone(score)

    def test_due_at_never_run(self):
        entry = self.create_entry(last_run_at=datetime.min)

        before = entry._default_now()
        due_at = entry.due_at
        after = entry._default_now()

        self.assertLess(before, due_at)
        self.assertLess(due_at, after)

    def test_due_at(self):
        # age last_run_at against a pinned clock so the old arithmetic
        # disagrees: it would land at now + 20s, not now + 40s
        now = datetime(2021, 9, 1, 0, 0, 20, tzinfo=timezone.utc)
        last_run_at = datetime(2021, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
        run_every = 60
        s = schedule(run_every=run_every, nowfun=lambda: now)
        entry = self.create_entry(s=s, last_run_at=last_run_at)

        due_at = entry.due_at

        self.assertEqual(due_at, now + timedelta(seconds=40))

    def test_due_at_remaining_estimate_from_now(self):
        # last ran at midnight, now 00:45, hourly -> due at 1am
        now = datetime(2021, 9, 1, 0, 45, 0, tzinfo=timezone.utc)
        last_run_at = datetime(2021, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
        s = schedule(run_every=3600, nowfun=lambda: now)

        entry = self.create_entry(s=s, last_run_at=last_run_at)

        self.assertEqual(entry.due_at, datetime(2021, 9, 1, 1, 0, 0, tzinfo=timezone.utc))

    def test_due_at_overdue(self):
        last_run_at = self.app.now() - timedelta(hours=10)
        entry = self.create_entry(last_run_at=last_run_at)

        before = entry._default_now()
        due_at = entry.due_at

        self.assertLess(last_run_at, due_at)
        self.assertGreater(due_at, before)

    def test_score(self):
        run_every = 61 * 60
        entry = self.create_entry(run_every=run_every)
        entry = entry._next_instance()

        score = entry.score
        expected = entry.last_run_at + timedelta(seconds=run_every)
        expected = expected.replace(microsecond=0)  # discard microseconds, lost in timestamp
        # 3.x returns naive, but 4.x returns aware
        expected = maybe_make_aware(expected)

        self.assertEqual(score, to_timestamp(expected))
        self.assertEqual(expected, from_timestamp(score))

    def test_generate_key(self) -> None:
        entry = self.create_entry()

        key = entry.generate_key(app=self.app, name="mock_task_name")

        self.assertEqual(key, "redbeat:mock_task_name")

    @patch.object(RedBeatSchedulerEntry, "generate_key")
    def test_key(self, mock_generate_key: MagicMock) -> None:
        entry = self.create_entry()

        key = entry.key

        mock_generate_key.assert_called_once_with(app=self.app, name="test")

        self.assertEqual(key, mock_generate_key.return_value)
