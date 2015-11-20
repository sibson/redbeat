from celery.tests.case import AppCase

from redbeat import RedBeatScheduler
from redbeat.schedulers import add_defaults


class RedBeatCase(AppCase):

    def setup(self):
        self.app.conf.add_defaults({
            'REDBEAT_REDIS_URL': 'redis://',
            'REDBEAT_KEY_PREFIX': 'rb-tests:',
        })
        add_defaults(self.app)


class test_RedBeatEntry(RedBeatCase):
    pass


class test_RedBeatScheduler(RedBeatCase):

    def test_empty_schedule(self):
        s = RedBeatScheduler(app=self.app)

        self.assertEqual(s.schedule, {})
        sleep = s.tick()
        self.assertEqual(sleep, s.max_interval)
