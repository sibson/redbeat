from unittest import TestCase

from celery.contrib.testing.app import TestApp
from celery.schedules import schedule
from fakeredis import FakeServer, FakeStrictRedis

from redbeat.schedulers import RedBeatSchedulerEntry


class AppCase(TestCase):
    def setUp(self):
        try:
            self.app = TestApp(config=self.config_dict)
        except Exception:
            self.app = TestApp()
        self.setup()


class RedBeatCase(AppCase):
    def setup(self):
        self.redis_server = FakeServer()
        self.app.conf.add_defaults(
            {'REDBEAT_KEY_PREFIX': 'rb-tests:', 'redbeat_key_prefix': 'rb-tests:'}
        )
        self.app.redbeat_redis = FakeStrictRedis(decode_responses=True, server=self.redis_server)
        self.app.redbeat_redis.flushdb()

    def create_entry(self, name=None, task=None, s=None, run_every=60, **kwargs):
        if name is None:
            name = 'test'

        if task is None:
            task = 'tasks.test'

        if s is None:
            s = schedule(run_every=run_every)

        e = RedBeatSchedulerEntry(name, task, s, app=self.app, **kwargs)

        return e
