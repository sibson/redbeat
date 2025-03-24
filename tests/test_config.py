from unittest import mock

from redbeat.schedulers import RedBeatConfig
from tests.basecase import AppCase


class test_RedBeatConfig(AppCase):
    def setup(self):
        self.conf = RedBeatConfig(self.app)

    def test_app(self):
        self.assertEqual(self.app, self.conf.app)

    def test_lock_timeout(self):
        # the config only has the lock_timeout if it was overidden
        # via the REDBEAT_LOCK_TIMEOUT, see test_scheduler.py for real test
        self.assertEqual(self.conf.lock_timeout, None)

    def test_key_prefix_default(self):
        self.assertEqual(self.conf.key_prefix, 'redbeat:')

    def test_other_keys(self):
        self.assertEqual(self.conf.schedule_key, self.conf.key_prefix + ':schedule')
        self.assertEqual(self.conf.statics_key, self.conf.key_prefix + ':statics')
        self.assertEqual(self.conf.lock_key, self.conf.key_prefix + ':lock')

    def test_key_prefix_override(self):
        self.app.conf.redbeat_key_prefix = 'test-prefix:'
        self.conf = RedBeatConfig(self.app)
        self.assertEqual(self.conf.key_prefix, 'test-prefix:')

    def test_lock_key_might_be_set_to_none(self):
        self.app.conf.redbeat_lock_key = None
        self.conf = RedBeatConfig(self.app)
        self.assertEqual(self.conf.lock_key, None)

    def test_lock_key_override(self):
        self.app.conf.redbeat_lock_key = ":custom"
        self.conf = RedBeatConfig(self.app)
        self.assertEqual(self.conf.lock_key, 'redbeat::custom')

    def test_schedule(self):
        schedule = {'foo': 'bar'}
        self.conf.schedule = schedule
        self.assertEqual(self.conf.schedule, schedule)

    @mock.patch('warnings.warn')
    def test_either_or(self, warn_mock):
        broker_url = self.conf.either_or('BROKER_URL')
        self.assertTrue(warn_mock.called)
        self.assertEqual(broker_url, self.app.conf.broker_url)
