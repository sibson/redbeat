# Licensed under the Apache License, Version 2.0 (the 'License'); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
# Copyright 2015 Marc Sibson


import redis.exceptions
from celery.utils.log import get_logger

logger = get_logger('celery.beat')

KEY_EXPIRY_CHECK_MODES = ('ignore', 'warn', 'error', 'raise')
DEFAULT_KEY_EXPIRY_CHECK = 'error'

EVICTABLE_MESSAGE = (
    "Redis%s is configured with maxmemory %s and maxmemory-policy '%s', which lets "
    "RedBeat's keys be evicted, silently stopping scheduled tasks; use the "
    "'noeviction' policy or give RedBeat a Redis instance or db of its own"
)


class RedBeatKeyExpiryError(RuntimeError):
    """Redis is configured to let RedBeat's keys be evicted."""


def check_key_expiry(client, mode=DEFAULT_KEY_EXPIRY_CHECK):
    """Report Redis configuration that lets RedBeat's keys disappear."""
    if mode == 'ignore':
        return []

    try:
        config = client.config_get('maxmemory*')
    except redis.exceptions.RedisError as exc:
        message = 'could not read the Redis maxmemory policy: %s' % exc
        if mode == 'raise':
            raise RedBeatKeyExpiryError(message)

        logger.warning('beat: %s', message)
        return []

    findings = _find_evictable_policies(config)
    if not findings:
        return []

    log = logger.warning if mode == 'warn' else logger.error
    for finding in findings:
        log('beat: %s', finding)

    if mode == 'raise':
        raise RedBeatKeyExpiryError('; '.join(findings))

    return findings


def _find_evictable_policies(config):
    evicting = {}
    for node, node_config in _per_node(config):
        try:
            maxmemory = int(node_config.get('maxmemory') or 0)
        except (AttributeError, TypeError, ValueError):
            continue

        if not maxmemory:
            # without a memory limit nothing is ever evicted, whatever the policy
            continue

        # volatile-* is safe, it only evicts keys carrying an expiry and the
        # lock, which is meant to expire, is the only RedBeat key that has one
        policy = (node_config.get('maxmemory-policy') or '').lower()
        if policy.startswith('allkeys'):
            evicting.setdefault((maxmemory, policy), []).append(node)

    return [
        EVICTABLE_MESSAGE % (_describe(nodes), maxmemory, policy)
        for (maxmemory, policy), nodes in evicting.items()
    ]


def _per_node(config):
    # a cluster client answers CONFIG GET with a reply per node
    if not isinstance(config, dict) or not config:
        return []

    if all(isinstance(value, dict) for value in config.values()):
        return sorted(config.items())

    return [('', config)]


def _describe(nodes):
    names = sorted(node for node in nodes if node)
    if not names:
        return ''

    return ' on node{} {}'.format('s' if len(names) > 1 else '', ', '.join(names))
