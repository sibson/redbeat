import mock
import pytest
from redbeat.schedulers import RedBeatConfig, CELERY_4_OR_GREATER

from basecase import AppCase


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

    def test_lock_key_default(self):
        self.assertTrue("REDBEAT_LOCK_KEY" not in self.app.conf.keys())
        self.assertTrue("redbeat_lock_key" not in self.app.conf.keys())
        self.conf = RedBeatConfig(self.app)
        self.assertEqual(self.conf.lock_key, 'redbeat::lock')

    def test_disable_lock_key_4(self):
        self.app.conf.redbeat_lock_key = None
        self.assertTrue("redbeat_lock_key" in self.app.conf.keys())
        self.conf = RedBeatConfig(self.app)
        self.assertEqual(self.conf.lock_key, None)

    def test_disable_lock_key_3(self):
        self.app.conf.REDBEAT_LOCK_KEY = None
        self.assertTrue("REDBEAT_LOCK_KEY" in self.app.conf.keys())
        self.conf = RedBeatConfig(self.app)
        self.assertEqual(self.conf.lock_key, None)

    def test_other_keys(self):
        self.assertEqual(self.conf.schedule_key, self.conf.key_prefix + ':schedule')
        self.assertEqual(self.conf.statics_key, self.conf.key_prefix + ':statics')
        self.assertEqual(self.conf.lock_key, self.conf.key_prefix + ':lock')

    @pytest.mark.skipif(not CELERY_4_OR_GREATER, reason="requires Celery >= 4.x")
    def test_key_prefix_override_4(self):
        self.app.conf.redbeat_key_prefix = 'test-prefix:'
        self.conf = RedBeatConfig(self.app)
        self.assertEqual(self.conf.key_prefix, 'test-prefix:')

    @pytest.mark.skipif(CELERY_4_OR_GREATER, reason="requires Celery < 4.x")
    def test_key_prefix_override_3(self):
        self.app.conf.REDBEAT_KEY_PREFIX = 'test-prefix:'
        self.conf = RedBeatConfig(self.app)
        self.assertEqual(self.conf.key_prefix, 'test-prefix:')

    def test_schedule(self):
        schedule = {'foo': 'bar'}
        self.conf.schedule = schedule
        self.assertEqual(self.conf.schedule, schedule)

    @pytest.mark.skipif(CELERY_4_OR_GREATER, reason="requires Celery < 4.x")
    @mock.patch('warnings.warn')
    def test_key_has_value_or_3(self, warn_mock):
        broker_url = self.conf.key_has_value_or('BROKER_URL')
        self.assertFalse(warn_mock.called)
        self.assertEqual(broker_url, self.app.conf.BROKER_URL)

    @pytest.mark.skipif(not CELERY_4_OR_GREATER, reason="requires Celery >= 4.x")
    @mock.patch('warnings.warn')
    def test_key_has_value_or_4(self, warn_mock):
        broker_url = self.conf.key_has_value_or('BROKER_URL')
        self.assertTrue(warn_mock.called)
        self.assertEqual(broker_url, self.app.conf.broker_url)
