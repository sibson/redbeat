from celery.tests.case import AppCase
from celery.schedules import schedule

from fakeredis import FakeStrictRedis
from redbeat import RedBeatSchedulerEntry
from redbeat.schedulers import add_defaults


class RedBeatCase(AppCase):

    def setup(self):
        self.app.conf.add_defaults({
            'REDBEAT_KEY_PREFIX': 'rb-tests:',
        })
        add_defaults(self.app)

        self.app.redbeat_redis = FakeStrictRedis()
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
