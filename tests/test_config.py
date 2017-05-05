import mock
import pytest
from redbeat.schedulers import RedBeatConfig, CELERY_4_OR_GREATER

from basecase import AppCase


class test_RedBeatConfig(AppCase):

    def setup(self):
        self.conf = RedBeatConfig(self.app)

    def test_app(self):
        self.assertEqual(self.app, self.conf.app)

    def test_max_loop_interval(self):
        self.app.conf[RedBeatConfig.max_loop_interval_config] = 12
        self.conf = RedBeatConfig(self.app)
        self.assertEqual(self.conf.max_loop_interval, 12)

    def test_lock_timeout(self):
        self.assertEqual(self.conf.lock_timeout, self.conf.max_loop_interval * 5)

    def test_key_prefix_default(self):
        self.assertEqual(self.conf.key_prefix, 'redbeat:')

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
    def test_either_or_3(self, warn_mock):
        broker_url = self.conf.either_or('BROKER_URL')
        self.assertFalse(warn_mock.called)
        self.assertEqual(broker_url, self.app.conf.BROKER_URL)

    @pytest.mark.skipif(not CELERY_4_OR_GREATER, reason="requires Celery >= 4.x")
    @mock.patch('warnings.warn')
    def test_either_or_4(self, warn_mock):
        broker_url = self.conf.either_or('BROKER_URL')
        self.assertTrue(warn_mock.called)
        self.assertEqual(broker_url, self.app.conf.broker_url)
