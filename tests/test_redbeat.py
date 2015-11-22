import json

from celery.schedules import schedule, crontab
from celery.tests.case import AppCase

from redbeat import RedBeatScheduler, RedBeatSchedulerEntry
from redbeat.schedulers import add_defaults, redis_client
from redbeat.decoder import RedBeatJSONDecoder, RedBeatJSONEncoder


class RedBeatCase(AppCase):

    def setup(self):
        self.app.conf.add_defaults({
            'REDBEAT_REDIS_URL': 'redis://',
            'REDBEAT_KEY_PREFIX': 'rb-tests:',
        })

        redis_client(self.app).flushdb()

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

        redis = redis_client(self.app)
        value = redis.hget(self.app.conf.REDBEAT_KEY_PREFIX + 'test', 'definition')
        self.assertEqual(expected, json.loads(value, cls=RedBeatJSONDecoder))
        self.assertEqual(redis.zrank(self.app.conf.REDBEAT_SCHEDULE_KEY, e.key), 0)
        self.assertEqual(redis.zscore(self.app.conf.REDBEAT_SCHEDULE_KEY, e.key), e.score)


class test_RedBeatScheduler(RedBeatCase):

    def test_empty_schedule(self):
        s = RedBeatScheduler(app=self.app)

        self.assertEqual(s.schedule, {})
        sleep = s.tick()
        self.assertEqual(sleep, s.max_interval)
