from unittest import TestCase
from unittest.mock import Mock

from redis.exceptions import ResponseError

from redbeat.checks import RedBeatKeyExpiryError, check_key_expiry


def client(maxmemory=0, policy='noeviction', config=None):
    if config is None:
        config = {'maxmemory': str(maxmemory), 'maxmemory-policy': policy}

    return Mock(config_get=Mock(return_value=config))


def unreadable_client():
    return Mock(config_get=Mock(side_effect=ResponseError("unknown command 'config get'")))


class test_key_expiry_check(TestCase):
    def test_nothing_to_report_by_default(self):
        self.assertEqual(check_key_expiry(client()), [])

    def test_evicting_policy_is_reported(self):
        findings = check_key_expiry(client(maxmemory=100000, policy='allkeys-lru'))

        self.assertEqual(len(findings), 1)
        self.assertIn('allkeys-lru', findings[0])

    def test_evicting_policy_without_a_memory_limit_is_ignored(self):
        self.assertEqual(check_key_expiry(client(maxmemory=0, policy='allkeys-lru')), [])

    def test_volatile_policy_is_ignored(self):
        self.assertEqual(check_key_expiry(client(maxmemory=100000, policy='volatile-lru')), [])

    def test_unparsable_maxmemory_is_ignored(self):
        config = {'maxmemory': 'lots', 'maxmemory-policy': 'allkeys-lru'}

        self.assertEqual(check_key_expiry(client(config=config)), [])

    def test_findings_are_logged_as_errors(self):
        with self.assertLogs('celery.beat', level='ERROR') as cm:
            check_key_expiry(client(maxmemory=100000, policy='allkeys-lru'))

        self.assertTrue(any('allkeys-lru' in message for message in cm.output))

    def test_warn_mode_logs_a_warning(self):
        with self.assertLogs('celery.beat', level='WARNING') as cm:
            check_key_expiry(client(maxmemory=100000, policy='allkeys-lru'), 'warn')

        self.assertTrue(all(record.startswith('WARNING') for record in cm.output))

    def test_raise_mode_raises(self):
        with self.assertRaises(RedBeatKeyExpiryError):
            check_key_expiry(client(maxmemory=100000, policy='allkeys-lru'), 'raise')

    def test_raise_mode_is_quiet_when_nothing_is_wrong(self):
        self.assertEqual(check_key_expiry(client(), 'raise'), [])

    def test_ignore_mode_asks_redis_nothing(self):
        redis = client(maxmemory=100000, policy='allkeys-lru')

        self.assertEqual(check_key_expiry(redis, 'ignore'), [])
        self.assertFalse(redis.config_get.called)


class test_unreadable_config(TestCase):
    def test_is_not_a_finding(self):
        with self.assertLogs('celery.beat', level='WARNING'):
            self.assertEqual(check_key_expiry(unreadable_client(), 'raise'), [])

    def test_is_logged_as_a_warning(self):
        with self.assertLogs('celery.beat', level='WARNING') as cm:
            check_key_expiry(unreadable_client())

        self.assertTrue(all(record.startswith('WARNING') for record in cm.output))

    def test_is_logged_as_an_error_in_raise_mode(self):
        with self.assertLogs('celery.beat', level='ERROR') as cm:
            check_key_expiry(unreadable_client(), 'raise')

        self.assertTrue(any('maxmemory policy' in message for message in cm.output))


class test_cluster_config(TestCase):
    def config(self, *policies):
        return {
            'node-{}'.format(number): {'maxmemory': '100000', 'maxmemory-policy': policy}
            for number, policy in enumerate(policies, start=1)
        }

    def test_reply_is_reported_per_node(self):
        findings = check_key_expiry(client(config=self.config('noeviction', 'allkeys-lfu')))

        self.assertEqual(len(findings), 1)
        self.assertIn('on node node-2', findings[0])
        self.assertIn('allkeys-lfu', findings[0])

    def test_nodes_sharing_a_policy_are_reported_once(self):
        findings = check_key_expiry(client(config=self.config('allkeys-lru', 'allkeys-lru')))

        self.assertEqual(len(findings), 1)
        self.assertIn('on nodes node-1, node-2', findings[0])

    def test_differing_policies_are_reported_separately(self):
        findings = check_key_expiry(client(config=self.config('allkeys-lru', 'allkeys-lfu')))

        self.assertEqual(len(findings), 2)
