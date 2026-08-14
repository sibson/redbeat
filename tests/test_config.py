import warnings
from unittest import mock

from celery.contrib.testing.app import TestApp

from redbeat.schedulers import RedBeatConfig, ensure_redis_hash_tag, has_redis_hash_tag
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

    def test_standalone_prefix_is_not_hash_tagged(self):
        self.assertFalse(has_redis_hash_tag(self.conf.key_prefix))
        self.assertEqual(self.conf.schedule_key, 'redbeat::schedule')

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


class test_BrokerFallbackDeprecation(AppCase):
    def setup(self):
        pass

    def deprecation_messages(self, config):
        app = TestApp(config=config)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            RedBeatConfig(app)
        return [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]

    def test_warns_when_inheriting_broker_settings(self):
        messages = self.deprecation_messages(
            {
                'BROKER_URL': 'redis://',
                'BROKER_TRANSPORT_OPTIONS': {'visibility_timeout': 3600},
            }
        )
        self.assertTrue(any('redbeat_redis_url' in m for m in messages))
        self.assertTrue(any('redbeat_redis_options' in m for m in messages))

    def test_no_warning_for_explicit_redbeat_settings(self):
        messages = self.deprecation_messages(
            {
                'redbeat_redis_url': 'redis://',
                'redbeat_redis_options': {'socket_timeout': 1},
            }
        )
        self.assertEqual(messages, [])

    def test_no_options_warning_when_broker_options_empty(self):
        messages = self.deprecation_messages({'redbeat_redis_url': 'redis://'})
        self.assertFalse(any('redbeat_redis_options' in m for m in messages))


class test_RedisClusterHashTags(AppCase):
    def setup(self):
        pass

    def test_ensure_wraps_untagged_prefix(self):
        self.assertEqual(ensure_redis_hash_tag('redbeat:'), '{redbeat:}')
        self.assertEqual(ensure_redis_hash_tag('redbeat_staging-'), '{redbeat_staging-}')

    def test_ensure_leaves_existing_tag_alone(self):
        self.assertEqual(ensure_redis_hash_tag('{redbeat:}'), '{redbeat:}')
        self.assertEqual(ensure_redis_hash_tag('env:{redbeat:}'), 'env:{redbeat:}')

    def test_empty_braces_are_not_a_tag(self):
        self.assertFalse(has_redis_hash_tag('{}prefix'))
        self.assertEqual(ensure_redis_hash_tag('{}prefix'), '{{}prefix}')

    def test_cluster_url_wraps_default_prefix(self):
        self.app.conf.redbeat_redis_url = 'redis-cluster://redis-cluster:30001/0'
        self.app.conf.redbeat_redis_options = {
            'startup_nodes': [{"host": "127.0.0.1", "port": 30001}],
        }
        conf = RedBeatConfig(self.app)
        self.assertEqual(conf.key_prefix, '{redbeat:}')
        self.assertEqual(conf.schedule_key, '{redbeat:}:schedule')
        self.assertEqual(conf.statics_key, '{redbeat:}:statics')
        self.assertEqual(conf.lock_key, '{redbeat:}:lock')

    def test_cluster_flag_wraps_custom_prefix(self):
        self.app.conf.redbeat_key_prefix = 'redbeat_staging-'
        self.app.conf.redbeat_redis_url = 'redis://localhost:6379/0'
        self.app.conf.redbeat_redis_options = {'cluster': True}
        conf = RedBeatConfig(self.app)
        self.assertEqual(conf.key_prefix, '{redbeat_staging-}')
        # entry hash and schedule ZSET must share the same tag (CROSSSLOT otherwise)
        entry_key = conf.key_prefix + 'removing_users'
        self.assertTrue(has_redis_hash_tag(entry_key))
        self.assertTrue(has_redis_hash_tag(conf.schedule_key))
        self.assertIn('{redbeat_staging-}', entry_key)
        self.assertIn('{redbeat_staging-}', conf.schedule_key)

    def test_cluster_respects_user_supplied_hash_tag(self):
        self.app.conf.redbeat_key_prefix = '{myapp:redbeat:}'
        self.app.conf.redbeat_redis_url = 'redis-cluster://redis-cluster:30001/0'
        self.app.conf.redbeat_redis_options = {
            'startup_nodes': [{"host": "127.0.0.1", "port": 30001}],
        }
        conf = RedBeatConfig(self.app)
        self.assertEqual(conf.key_prefix, '{myapp:redbeat:}')
        self.assertEqual(conf.schedule_key, '{myapp:redbeat:}:schedule')
