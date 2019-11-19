import pytz
from copy import deepcopy
from datetime import datetime, timedelta
import unittest

from celery.schedules import (
    schedule,
    schedstate
)
from celery.utils.time import maybe_timedelta
import celery.contrib.testing.app

from mock import (
    patch,
    Mock
)
from basecase import RedBeatCase, AppCase
from redbeat import RedBeatScheduler
from redbeat.schedulers import get_redis

import ssl

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
        super(RedBeatSchedulerTestBase, self).setUp()
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

    def test_empty(self):
        with patch.object(self.s, 'send_task') as send_task:
            sleep = self.s.tick()
            self.assertFalse(send_task.called)

        self.assertEqual(sleep, self.s.max_interval)

    def test_due_next_never_run(self):
        e = self.create_entry(name='next', s=due_next).save()

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
        schedule = {
            'test': {
                'task': 'test',
                'schedule': mocked_schedule(42)
            }
        }
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


class NotSentinelRedBeatCase(AppCase):

    config_dict = {
        'BROKER_URL': 'redis://',
    }

    def setup(self):
        self.app.conf.update(self.config_dict)

    def test_sentinel_scheduler(self):
        redis_client = get_redis(app=self.app)
        assert 'Sentinel' not in str(redis_client.connection_pool)

class SentinelRedBeatCase(AppCase):

    config_dict = {
            'REDBEAT_KEY_PREFIX': 'rb-tests:',
            'redbeat_key_prefix': 'rb-tests:',
            'BROKER_URL': 'redis-sentinel://redis-sentinel:26379/0',
            'BROKER_TRANSPORT_OPTIONS': {
                'sentinels': [('192.168.1.1', 26379),
                              ('192.168.1.2', 26379),
                              ('192.168.1.3', 26379)],
                'service_name': 'master',
                'socket_timeout': 0.1,
            },
            'CELERY_RESULT_BACKEND' : 'redis-sentinel://redis-sentinel:26379/1',
        }

    def Celery(self, *args, **kwargs):
        return UnitApp(*args, broker='redis-sentinel://redis-sentinel:26379/0', **kwargs)

    def setup(self): # celery3
        self.app.conf.add_defaults(deepcopy(self.config_dict))

    def test_sentinel_scheduler(self):
        redis_client = get_redis(app=self.app)
        assert 'Sentinel' in str(redis_client.connection_pool)


class SeparateOptionsForSchedulerCase(AppCase):

    config_dict = {
            'REDBEAT_KEY_PREFIX': 'rb-tests:',
            'REDBEAT_REDIS_URL': 'redis-sentinel://redis-sentinel:26379/0',
            'REDBEAT_REDIS_OPTIONS': {
                'sentinels': [('192.168.1.1', 26379),
                              ('192.168.1.2', 26379),
                              ('192.168.1.3', 26379)],
                'password': '123',
                'service_name': 'master',
                'socket_timeout': 0.1,
            },
            'CELERY_RESULT_BACKEND' : 'redis-sentinel://redis-sentinel:26379/1',
        }

    def Celery(self, *args, **kwargs):
        return UnitApp(*args, broker='redis-sentinel://redis-sentinel:26379/0', **kwargs)

    def setup(self): # celery3
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
            'CELERY_RESULT_BACKEND' : 'redis-sentinel://redis-sentinel:26379/1',
            'REDBEAT_REDIS_USE_SSL': {
                'ssl_cert_reqs': ssl.CERT_REQUIRED,
                'ssl_keyfile': '/path/to/file.key',
                'ssl_certfile': '/path/to/cert.pem',
                'ssl_ca_certs': '/path/to/ca.pem',
            },
        }

    def Celery(self, *args, **kwargs):
        return UnitApp(*args, broker='rediss://redishost:26379/0', **kwargs)

    def setup(self): # celery3
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
            'CELERY_RESULT_BACKEND' : 'redis-sentinel://redis-sentinel:26379/1',
            'BROKER_USE_SSL': {
                'ssl_cert_reqs': ssl.CERT_REQUIRED,
                'ssl_keyfile': '/path/to/file.key',
                'ssl_certfile': '/path/to/cert.pem',
                'ssl_ca_certs': '/path/to/ca.pem',
            },
        }

    def Celery(self, *args, **kwargs):
        return UnitApp(*args, broker='rediss://redishost:26379/0', **kwargs)

    def setup(self): # celery3
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
            'CELERY_RESULT_BACKEND' : 'redis-sentinel://redis-sentinel:26379/1',
            'REDBEAT_REDIS_USE_SSL': True
        }

    def Celery(self, *args, **kwargs):
        return UnitApp(*args, broker='rediss://redishost:26379/0', **kwargs)

    def setup(self): # celery3
        self.app.conf.add_defaults(deepcopy(self.config_dict))

    def test_ssl_connection_scheduler(self):
        redis_client = get_redis(app=self.app)
        assert 'SSLConnection' in str(redis_client.connection_pool)
        assert redis_client.connection_pool.connection_kwargs['ssl_cert_reqs'] == ssl.CERT_REQUIRED
        assert 'ssl_keyfile' not in redis_client.connection_pool.connection_kwargs
        assert 'ssl_certfile' not in redis_client.connection_pool.connection_kwargs
        assert 'ssl_ca_certs' not in redis_client.connection_pool.connection_kwargs

