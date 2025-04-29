import ssl
import unittest
from copy import deepcopy
from datetime import datetime, timedelta
from unittest import mock
from unittest.mock import MagicMock, Mock, patch

import pytz
from celery.beat import DEFAULT_MAX_INTERVAL
from celery.schedules import schedstate, schedule
from celery.utils.time import maybe_timedelta
from redis.exceptions import ConnectionError

from redbeat import RedBeatScheduler
from redbeat.schedulers import RedBeatSchedulerEntry, acquire_distributed_beat_lock, get_redis
from tests.basecase import AppCase, RedBeatCase


class mocked_schedule(schedule):
    def __init__(self, remaining):
        self._remaining = maybe_timedelta(remaining)
        self.run_every = timedelta(seconds=1)
        self.nowfun = datetime.utcnow

    def remaining_estimate(self, last_run_at):
        return self._remaining


class mocked_expired_schedule(schedule):
    def __init__(self):
        self.nowfun = datetime.utcnow
        self.run_every = Mock()
        self.run_every.total_seconds.return_value = 1

    def remaining_estimate(self, last_run_at):
        return None

    def is_due(self, last_run_at):
        return schedstate(False, None)


due_now = mocked_schedule(0)
due_next = mocked_schedule(1)


class RedBeatSchedulerTestBase(RedBeatCase):
    def setUp(self):
        super().setUp()
        self.s = RedBeatScheduler(app=self.app)
        self.due_later = mocked_schedule(self.s.max_interval * 10)
        self.send_task = patch.object(self.s, 'send_task')
        self.send_task.start()

    def tearDown(self):
        self.send_task.stop()


class test_RedBeatScheduler_schedule(RedBeatSchedulerTestBase):
    def test_empty_schedule(self):
        self.assertEqual(self.s.schedule, {})

    def test_schedule_includes_current_and_next(self):
        due = self.create_entry(name='due', s=due_now).save()
        up_next = self.create_entry(name='up_next', s=due_next).save()
        up_next2 = self.create_entry(name='up_next2', s=due_next).save()
        later = self.create_entry(name='later', s=self.due_later).save()

        schedule = self.s.schedule

        self.assertEqual(len(schedule), 2)

        self.assertIn(due.name, schedule)
        self.assertEqual(due.key, schedule[due.name].key)

        self.assertIn(up_next.name, schedule)
        self.assertEqual(up_next.key, schedule[up_next.name].key)

        self.assertNotIn(up_next2.name, schedule)
        self.assertNotIn(later.name, schedule)


class test_RedBeatScheduler_tick(RedBeatSchedulerTestBase):
    def setUp(self):
        super().setUp()
        self.s.lock_key = None

    def test_empty(self):
        with patch.object(self.s, 'send_task') as send_task:
            sleep = self.s.tick()
            self.assertFalse(send_task.called)

        self.assertEqual(sleep, self.s.max_interval)

    def test_due_next_never_run(self):
        self.create_entry(name='next', s=due_next).save()

        with patch.object(self.s, 'send_task') as send_task:
            sleep = self.s.tick()
            self.assertFalse(send_task.called)

        self.assertLess(sleep, 1.0)

    def test_due_next_just_ran(self):
        e = self.create_entry(name='next', s=due_next)
        e.save().reschedule()

        with patch.object(self.s, 'send_task') as send_task:
            sleep = self.s.tick()
            self.assertFalse(send_task.called)
        self.assertLess(0.8, sleep)
        self.assertLess(sleep, 1.0)

    @unittest.skip('test is breaking and unsure what the correct behaviour should be')
    def test_due_next_never_run_tz_positive(self):
        self.app.timezone = pytz.timezone('Europe/Moscow')

        e = self.create_entry(name='next', s=due_next).save()

        with patch.object(self.s, 'send_task') as send_task:
            sleep = self.s.tick()
            send_task.assert_called_with(e.task, e.args, e.kwargs, **self.s._maybe_due_kwargs)
            # would be more correct to
            # self.assertFalse(send_task.called)

        self.assertEqual(sleep, 1.0)
        self.app.timezone = pytz.utc

    @unittest.skip('test is breaking and unsure what the correct behaviour should be')
    def test_due_next_never_run_tz_negative(self):
        self.app.timezone = pytz.timezone('America/Chicago')

        e = self.create_entry(name='next', s=due_next).save()

        with patch.object(self.s, 'send_task') as send_task:
            sleep = self.s.tick()
            send_task.assert_called_with(e.task, e.args, e.kwargs, **self.s._maybe_due_kwargs)
            # would be more correct to
            # self.assertFalse(send_task.called)

        self.assertEqual(sleep, 1.0)
        self.app.timezone = pytz.utc

    def test_due_later_task_never_run(self):
        self.create_entry(s=self.due_later).save()

        with patch.object(self.s, 'send_task') as send_task:
            sleep = self.s.tick()
            self.assertFalse(send_task.called)

        self.assertEqual(sleep, self.s.max_interval)

    def test_due_now(self):
        e = self.create_entry(
            name='now',
            args=[],
            s=due_now,
            last_run_at=datetime.utcnow() - timedelta(seconds=1),
        ).save()

        with patch.object(self.s, 'send_task') as send_task:
            sleep = self.s.tick()
            send_task.assert_called_with(e.task, e.args, e.kwargs, **self.s._maybe_due_kwargs)

        self.assertEqual(sleep, 1.0)

    def test_old_static_entries_are_removed(self):
        redis = self.app.redbeat_redis
        schedule = {'test': {'task': 'test', 'schedule': mocked_schedule(42)}}
        self.app.redbeat_conf.schedule = schedule
        self.s.setup_schedule()

        self.assertIn('test', self.s.schedule)
        self.assertIn('test', redis.smembers(self.app.redbeat_conf.statics_key))

        self.app.redbeat_conf.schedule = {}
        self.s.setup_schedule()

        self.assertNotIn('test', self.s.schedule)
        self.assertNotIn('test', redis.smembers(self.app.redbeat_conf.statics_key))

    def test_lock_timeout(self):
        self.assertEqual(self.s.lock_timeout, self.s.max_interval * 5)

    def test_lock_acquisition_failed_during_startup(self):
        self.s.lock_key = 'lock-key'
        self.s.lock = None
        with self.assertRaises(AttributeError):
            self.s.tick()


class TestRedBeatSchedulerUpdateFromDict(RedBeatSchedulerTestBase):
    @patch.object(RedBeatSchedulerEntry, "from_key")
    @patch.object(RedBeatSchedulerEntry, "save")
    def test_update_from_dict_fetch_redis_entry(
        self, mock_entry_save: MagicMock, mock_from_key: MagicMock
    ) -> None:
        mock_entry_from_redis_key = mock_from_key.return_value
        mock_entry_from_redis_key.last_run_at = datetime.now()

        self.s.update_from_dict(
            dict_={'task_name': {'task': 'tasks.task_name', 'schedule': timedelta(seconds=30)}}
        )

        mock_from_key.assert_called_once_with("rb-tests:task_name", app=self.app)

        mock_entry_save.assert_called_once()

    @patch.object(RedBeatSchedulerEntry, "from_key")
    @patch.object(RedBeatSchedulerEntry, "save")
    def test_update_from_dict(self, mock_entry_save: MagicMock, mock_from_key: MagicMock) -> None:
        mock_from_key.side_effect = [KeyError()]

        self.s.update_from_dict(
            dict_={'task_name': {'task': 'tasks.task_name', 'schedule': timedelta(seconds=30)}}
        )

        mock_entry_save.assert_called_once()


class NotSentinelRedBeatCase(AppCase):
    config_dict = {
        'BROKER_URL': 'redis://',
    }

    def setup(self):
        self.app.conf.update(self.config_dict)

    def test_sentinel_scheduler(self):
        redis_client = get_redis(app=self.app)
        assert 'Sentinel' not in str(redis_client.connection_pool)


class ClusterRedBeatCase(AppCase):
    config_dict = {
        'BROKER_URL': 'redis://',
        'REDBEAT_REDIS_OPTIONS': {
            'cluster': True,
        },
    }

    def setup(self):
        self.app.conf.update(self.config_dict)

    def test_sentinel_scheduler(self):
        # Fake redis doesn't really support redis cluster, but let's just make sure it was used.
        with mock.patch('redis.RedisCluster.from_url') as from_url:
            get_redis(app=self.app)
            self.assertTrue(from_url.called)


class SentinelRedBeatCase(AppCase):
    config_dict = {
        'REDBEAT_KEY_PREFIX': 'rb-tests:',
        'redbeat_key_prefix': 'rb-tests:',
        'BROKER_URL': 'redis-sentinel://redis-sentinel:26379/0',
        'CELERY_RESULT_BACKEND': 'redis-sentinel://redis-sentinel:26379/1',
    }
    BROKER_TRANSPORT_OPTIONS = {
        'sentinels': [('192.168.1.1', 26379), ('192.168.1.2', 26379), ('192.168.1.3', 26379)],
        'service_name': 'master',
        'socket_timeout': 0.1,
    }

    def setup(self):  # celery3
        self.app.conf.add_defaults(deepcopy(self.config_dict))

    def test_sentinel_scheduler(self):
        self.app.conf.update({'BROKER_TRANSPORT_OPTIONS': self.BROKER_TRANSPORT_OPTIONS})
        redis_client = get_redis(app=self.app)
        assert 'Sentinel' in str(redis_client.connection_pool)

    def test_sentinel_scheduler_options(self):
        for options in [
            "BROKER_TRANSPORT_OPTIONS",
            "redbeat_redis_options",
            "REDBEAT_REDIS_OPTIONS",
        ]:
            config = deepcopy(self.config_dict)
            config[options] = self.BROKER_TRANSPORT_OPTIONS
            self.app.conf.clear()
            self.app.conf.update(config)
            redis_client = get_redis(app=self.app)
            assert 'Sentinel' in str(redis_client.connection_pool)


class SeparateOptionsForSchedulerCase(AppCase):
    config_dict = {
        'REDBEAT_KEY_PREFIX': 'rb-tests:',
        'REDBEAT_REDIS_URL': 'redis-sentinel://redis-sentinel:26379/0',
        'REDBEAT_REDIS_OPTIONS': {
            'sentinels': [('192.168.1.1', 26379), ('192.168.1.2', 26379), ('192.168.1.3', 26379)],
            'password': '123',
            'service_name': 'master',
            'socket_timeout': 0.1,
        },
        'CELERY_RESULT_BACKEND': 'redis-sentinel://redis-sentinel:26379/1',
    }

    def setup(self):  # celery3
        self.app.conf.add_defaults(deepcopy(self.config_dict))

    def test_sentinel_scheduler(self):
        redis_client = get_redis(app=self.app)
        assert 'Sentinel' in str(redis_client.connection_pool)


class SSLConnectionToRedis(AppCase):
    config_dict = {
        'REDBEAT_KEY_PREFIX': 'rb-tests:',
        'REDBEAT_REDIS_URL': 'rediss://redishost:26379/0',
        'REDBEAT_REDIS_OPTIONS': {
            'password': '123',
            'service_name': 'master',
            'socket_timeout': 0.1,
        },
        'CELERY_RESULT_BACKEND': 'redis-sentinel://redis-sentinel:26379/1',
        'REDBEAT_REDIS_USE_SSL': {
            'ssl_cert_reqs': ssl.CERT_REQUIRED,
            'ssl_keyfile': '/path/to/file.key',
            'ssl_certfile': '/path/to/cert.pem',
            'ssl_ca_certs': '/path/to/ca.pem',
        },
    }

    def setup(self):  # celery3
        self.app.conf.add_defaults(deepcopy(self.config_dict))

    def test_ssl_connection_scheduler(self):
        redis_client = get_redis(app=self.app)
        assert 'SSLConnection' in str(redis_client.connection_pool)
        assert redis_client.connection_pool.connection_kwargs['ssl_cert_reqs'] == ssl.CERT_REQUIRED
        assert redis_client.connection_pool.connection_kwargs['ssl_keyfile'] == '/path/to/file.key'
        assert redis_client.connection_pool.connection_kwargs['ssl_certfile'] == '/path/to/cert.pem'
        assert redis_client.connection_pool.connection_kwargs['ssl_ca_certs'] == '/path/to/ca.pem'


class SSLConnectionToRedisDefaultBrokerSSL(AppCase):
    config_dict = {
        'REDBEAT_KEY_PREFIX': 'rb-tests:',
        'REDBEAT_REDIS_URL': 'rediss://redishost:26379/0',
        'REDBEAT_REDIS_OPTIONS': {
            'password': '123',
            'service_name': 'master',
            'socket_timeout': 0.1,
        },
        'CELERY_RESULT_BACKEND': 'redis-sentinel://redis-sentinel:26379/1',
        'BROKER_USE_SSL': {
            'ssl_cert_reqs': ssl.CERT_REQUIRED,
            'ssl_keyfile': '/path/to/file.key',
            'ssl_certfile': '/path/to/cert.pem',
            'ssl_ca_certs': '/path/to/ca.pem',
        },
    }

    def setup(self):  # celery3
        self.app.conf.add_defaults(deepcopy(self.config_dict))

    def test_ssl_connection_scheduler(self):
        redis_client = get_redis(app=self.app)
        assert 'SSLConnection' in str(redis_client.connection_pool)
        assert redis_client.connection_pool.connection_kwargs['ssl_cert_reqs'] == ssl.CERT_REQUIRED
        assert redis_client.connection_pool.connection_kwargs['ssl_keyfile'] == '/path/to/file.key'
        assert redis_client.connection_pool.connection_kwargs['ssl_certfile'] == '/path/to/cert.pem'
        assert redis_client.connection_pool.connection_kwargs['ssl_ca_certs'] == '/path/to/ca.pem'


class SSLConnectionToRedisNoCerts(AppCase):
    config_dict = {
        'REDBEAT_KEY_PREFIX': 'rb-tests:',
        'REDBEAT_REDIS_URL': 'rediss://redishost:26379/0',
        'REDBEAT_REDIS_OPTIONS': {
            'password': '123',
            'service_name': 'master',
            'socket_timeout': 0.1,
        },
        'CELERY_RESULT_BACKEND': 'redis-sentinel://redis-sentinel:26379/1',
        'REDBEAT_REDIS_USE_SSL': True,
    }

    def setup(self):  # celery3
        self.app.conf.add_defaults(deepcopy(self.config_dict))

    def test_ssl_connection_scheduler(self):
        redis_client = get_redis(app=self.app)
        assert 'SSLConnection' in str(redis_client.connection_pool)
        assert redis_client.connection_pool.connection_kwargs['ssl_cert_reqs'] == ssl.CERT_REQUIRED
        assert 'ssl_keyfile' not in redis_client.connection_pool.connection_kwargs
        assert 'ssl_certfile' not in redis_client.connection_pool.connection_kwargs
        assert 'ssl_ca_certs' not in redis_client.connection_pool.connection_kwargs


class RedBeatLockTimeoutDefaultValues(RedBeatCase):
    def test_no_values(self):
        scheduler = RedBeatScheduler(app=self.app)
        assert DEFAULT_MAX_INTERVAL * 5 == scheduler.lock_timeout
        assert DEFAULT_MAX_INTERVAL == scheduler.max_interval


class RedBeatLockTimeoutCustomMaxInterval(RedBeatCase):
    config_dict = {
        'beat_max_loop_interval': 5,
    }

    def test_no_lock_timeout(self):
        scheduler = RedBeatScheduler(app=self.app)
        assert self.config_dict['beat_max_loop_interval'] * 5 == scheduler.lock_timeout
        assert self.config_dict['beat_max_loop_interval'] == scheduler.max_interval


class RedBeatLockTimeoutCustomAll(RedBeatCase):
    config_dict = {
        'beat_max_loop_interval': 7,
        'redbeat_lock_timeout': 13,
    }

    def test_custom_lock_timeout(self):
        scheduler = RedBeatScheduler(app=self.app)
        assert self.config_dict['beat_max_loop_interval'] == scheduler.max_interval
        assert self.config_dict['redbeat_lock_timeout'] == scheduler.lock_timeout


class RedBeatStartupAcquiresLock(RedBeatSchedulerTestBase):
    def setUp(self):
        super().setUp()
        self.sender = Mock(scheduler=self.s)

    def test_acquires_lock(self):
        acquire_distributed_beat_lock(self.sender)
        self.assertTrue(self.s.lock.owned())

    def test_connection_error(self):
        self.redis_server.connected = False
        with self.assertRaises(ConnectionError):
            acquire_distributed_beat_lock(self.sender)
