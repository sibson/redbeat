from datetime import datetime
import json

from celery.schedules import schedule, crontab
from celery.tests.case import AppCase

from fakeredis import FakeStrictRedis

from redbeat import RedBeatScheduler, RedBeatSchedulerEntry
from redbeat.schedulers import add_defaults
from redbeat.decoder import RedBeatJSONDecoder, RedBeatJSONEncoder


class RedBeatCase(AppCase):

    def setup(self):
        self.app.conf.add_defaults({
            'REDBEAT_KEY_PREFIX': 'rb-tests:',
        })

        self.app.redbeat_redis = FakeStrictRedis()
        self.app.redbeat_redis.flushdb()

        add_defaults(self.app)


class test_RedBeatEntry(RedBeatCase):

    def test_basic_save(self):
        s = schedule(run_every=60)
        e = RedBeatSchedulerEntry('test', 'tasks.test', s, app=self.app)
        e.save()

        expected = {
            'name': 'test',
            'task': 'tasks.test',
            'schedule': s,
            'args': None,
            'kwargs': None,
            'options': {},
            'enabled': True,
        }

        redis = self.app.redbeat_redis
        value = redis.hget(self.app.conf.REDBEAT_KEY_PREFIX + 'test', 'definition')
        self.assertEqual(expected, json.loads(value, cls=RedBeatJSONDecoder))
        self.assertEqual(redis.zrank(self.app.conf.REDBEAT_SCHEDULE_KEY, e.key), 0)
        self.assertEqual(redis.zscore(self.app.conf.REDBEAT_SCHEDULE_KEY, e.key), e.score)

    def test_load_meta_nonexistent_key(self):
        meta = RedBeatSchedulerEntry.load_meta('doesntexist', self.app)
        self.assertEqual(meta, {'last_run_at': datetime.min})

    def test_load_definition_nonexistent_key(self):
        with self.assertRaises(KeyError):
            RedBeatSchedulerEntry.load_definition('doesntexist', self.app)

    def test_from_key_nonexistent_key(self):
        with self.assertRaises(KeyError):
            RedBeatSchedulerEntry.from_key('doesntexist', self.app)

    def test_next(self):
        s = schedule(run_every=10)
        initial = RedBeatSchedulerEntry('test', 'tasks.test', s, app=self.app)

        n = next(initial)

        # TODO flesh out test


class test_RedBeatScheduler(RedBeatCase):

    def test_empty_schedule(self):
        s = RedBeatScheduler(app=self.app)

        self.assertEqual(s.schedule, {})
        sleep = s.tick()
        self.assertEqual(sleep, s.max_interval)
