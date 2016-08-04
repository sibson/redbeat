from datetime import datetime, timedelta
import json

from basecase import RedBeatCase

from redbeat import RedBeatSchedulerEntry
from redbeat.decoder import RedBeatJSONDecoder, RedBeatJSONEncoder
from redbeat.schedulers import to_timestamp, from_timestamp


class test_RedBeatEntry(RedBeatCase):

    def test_basic_save(self):
        e = self.create_entry()
        e.save()

        expected = {
            'name': 'test',
            'task': 'tasks.test',
            'schedule': e.schedule,
            'args': None,
            'kwargs': None,
            'options': {},
            'enabled': True,
        }
        expected_key = (self.app.conf.REDBEAT_KEY_PREFIX + 'test').encode('utf-8')

        redis = self.app.redbeat_redis
        value = redis.hget(expected_key, 'definition').decode('utf8')
        self.assertEqual(expected, json.loads(value, cls=RedBeatJSONDecoder))
        self.assertEqual(redis.zrank(self.app.conf.REDBEAT_SCHEDULE_KEY, e.key), 0)
        self.assertEqual(redis.zscore(self.app.conf.REDBEAT_SCHEDULE_KEY, e.key), e.score)

    def test_from_key_nonexistent_key(self):
        with self.assertRaises(KeyError):
            RedBeatSchedulerEntry.from_key('doesntexist', self.app)

    def test_from_key_missing_meta(self):
        initial = self.create_entry().save()

        loaded = RedBeatSchedulerEntry.from_key(initial.key, self.app)
        self.assertEqual(initial.task, loaded.task)
        self.assertEqual(loaded.last_run_at, datetime.min)

    def test_next(self):
        initial = self.create_entry().save()
        now = self.app.now()

        n = initial.next(last_run_at=now)

        # new entry has updated run info
        self.assertNotEqual(initial, n)
        self.assertEqual(n.last_run_at, now)
        self.assertEqual(initial.total_run_count + 1, n.total_run_count)

        # updated meta was stored into redis
        loaded = RedBeatSchedulerEntry.from_key(initial.key, app=self.app)
        self.assertEqual(loaded.last_run_at, now)
        self.assertEqual(loaded.total_run_count, initial.total_run_count + 1)

        # new entry updated the schedule
        redis = self.app.redbeat_redis
        self.assertEqual(redis.zscore(self.app.conf.REDBEAT_SCHEDULE_KEY, n.key), n.score)

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

        score = self.app.redbeat_redis.zrank(self.app.conf.REDBEAT_SCHEDULE_KEY, initial.key)
        self.assertIsNone(score)

    def test_due_at_never_run(self):
        entry = self.create_entry(last_run_at=datetime.min)

        before = entry._default_now()
        due_at = entry.due_at
        after = entry._default_now()

        self.assertLess(before, due_at)
        self.assertLess(due_at, after)

    def test_due_at(self):
        entry = self.create_entry()

        now = entry._default_now()

        entry.last_run_at = now
        due_at = entry.due_at

        self.assertLess(now, due_at)
        self.assertLess(due_at, now + entry.schedule.run_every)

    def test_due_at_overdue(self):
        last_run_at = self.app.now() - timedelta(hours=10)
        entry = self.create_entry(last_run_at=last_run_at)

        before = entry._default_now()
        due_at = entry.due_at

        self.assertLess(last_run_at, due_at)
        self.assertGreater(due_at, before)

    def test_score(self):
        run_every = 61*60
        entry = self.create_entry(run_every=run_every)
        entry = entry._next_instance()

        score = entry.score
        expected = entry.last_run_at + timedelta(seconds=run_every)
        expected = expected.replace(microsecond=0)  # discard microseconds, lost in timestamp

        self.assertEqual(score, to_timestamp(expected))
        self.assertEqual(expected, from_timestamp(score))
