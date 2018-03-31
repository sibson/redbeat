# Licensed under the Apache License, Version 2.0 (the 'License'); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
# Copyright 2015 Marc Sibson

from __future__ import absolute_import

import calendar
import warnings
from datetime import datetime, MINYEAR

try:
    import simplejson as json
except ImportError:
    import json

from packaging.version import parse as parse_version
from celery import __version__ as celery_version
from celery.beat import Scheduler, ScheduleEntry, DEFAULT_MAX_INTERVAL
from celery.utils.log import get_logger
from celery.signals import beat_init
try:  # celery 3.x
    from celery.utils.timeutils import humanize_seconds, timezone
    from kombu.utils import cached_property
except ImportError:  # celery 4.x
    from celery.utils.time import humanize_seconds, timezone
    from kombu.utils.objects import cached_property
from celery.app import app_or_default
from celery.five import values
from kombu.utils.url import maybe_sanitize_url

from redis.client import StrictRedis

from .decoder import (
    RedBeatJSONEncoder, RedBeatJSONDecoder,
    from_timestamp, to_timestamp
    )

CELERY_4_OR_GREATER = parse_version(celery_version) >= parse_version('4.0')


def ensure_conf(app):
    """
    Ensure for the given app the the redbeat_conf
    attribute is set to an instance of the RedBeatConfig
    class.
    """
    name = 'redbeat_conf'
    app = app_or_default(app)
    try:
        config = getattr(app, name)
    except AttributeError:
        config = RedBeatConfig(app)
        setattr(app, name, config)
    return config


def redis(app=None):
    app = app_or_default(app)
    conf = ensure_conf(app)
    if not hasattr(app, 'redbeat_redis') or app.redbeat_redis is None:
        redis_options = conf.app.conf.get(
            'REDBEAT_REDIS_OPTIONS',
            conf.app.conf.get('BROKER_TRANSPORT_OPTIONS', {}))
        if conf.redis_url.startswith('redis-sentinel') and  'sentinels' in redis_options:
            from redis.sentinel import Sentinel
            sentinel = Sentinel(redis_options['sentinels'],
                                socket_timeout=redis_options.get('socket_timeout'),
                                password=redis_options.get('password'),
                                decode_responses=True)
            app.redbeat_redis = sentinel.master_for(redis_options.get('service_name', 'master'))
        else:
            app.redbeat_redis = StrictRedis.from_url(conf.redis_url,
                                                     decode_responses=True)

    return app.redbeat_redis


ADD_ENTRY_ERROR = """\

Couldn't add entry %r to redis schedule: %r. Contents: %r
"""

logger = get_logger(__name__)


class RedBeatConfig(object):
    def __init__(self, app=None):
        self.app = app_or_default(app)
        self.key_prefix = self.either_or('redbeat_key_prefix', 'redbeat:')
        self.schedule_key = self.key_prefix + ':schedule'
        self.statics_key = self.key_prefix + ':statics'
        self.lock_key = self.either_or('redbeat_lock_key', self.key_prefix + ':lock')
        self.lock_timeout = self.either_or('redbeat_lock_timeout', None)
        self.redis_url = self.either_or('redbeat_redis_url', app.conf['BROKER_URL'])

    @property
    def schedule(self):
        if CELERY_4_OR_GREATER:
            return self.app.conf.beat_schedule
        else:
            return self.app.conf.CELERYBEAT_SCHEDULE

    @schedule.setter
    def schedule(self, value):
        if CELERY_4_OR_GREATER:
            self.app.conf.beat_schedule = value
        else:
            self.app.conf.CELERYBEAT_SCHEDULE = value

    def either_or(self, name, default=None):
        if CELERY_4_OR_GREATER and name == name.upper():
            warnings.warn(
                'Celery v4 installed, but detected Celery v3 '
                'configuration %s (use %s instead).' % (name, name.lower()),
                UserWarning
            )
        return self.app.conf.first(name, name.upper()) or default


class RedBeatSchedulerEntry(ScheduleEntry):
    _meta = None

    def __init__(self, name=None, task=None, schedule=None,
                 args=None, kwargs=None, enabled=True, **clsargs):
        super(RedBeatSchedulerEntry, self).__init__(name=name, task=task, schedule=schedule,
                                                    args=args, kwargs=kwargs, **clsargs)
        self.enabled = enabled
        ensure_conf(self.app)

    @staticmethod
    def load_definition(key, app=None, definition=None):
        if definition is None:
            definition = redis(app).hget(key, 'definition')

        if not definition:
            raise KeyError(key)

        definition = RedBeatSchedulerEntry.decode_definition(definition)

        return definition

    @staticmethod
    def decode_definition(definition):
        return json.loads(definition, cls=RedBeatJSONDecoder)

    @staticmethod
    def load_meta(key, app=None):
        return RedBeatSchedulerEntry.decode_meta(redis(app).hget(key, 'meta'))

    @staticmethod
    def decode_meta(meta, app=None):
        if not meta:
            return {'last_run_at': None}

        return json.loads(meta, cls=RedBeatJSONDecoder)

    @classmethod
    def from_key(cls, key, app=None):
        ensure_conf(app)
        with redis(app).pipeline() as pipe:
            pipe.hget(key, 'definition')
            pipe.hget(key, 'meta')
            definition, meta = pipe.execute()

        if not definition:
            raise KeyError(key)

        definition = cls.decode_definition(definition)
        meta = cls.decode_meta(meta)
        definition.update(meta)

        entry = cls(app=app, **definition)
        # celery.ScheduleEntry sets last_run_at = utcnow(), which is confusing and wrong
        entry.last_run_at = meta['last_run_at']

        return entry

    @property
    def due_at(self):
        # never run => due now
        if self.last_run_at is None:
            return self._default_now()

        delta = self.schedule.remaining_estimate(self.last_run_at)
        # if no delta, means no more events after the last_run_at.
        if delta is None:
            return None

        # overdue => due now
        if delta.total_seconds() < 0:
            return self._default_now()

        return self.last_run_at + delta

    @property
    def key(self):
        return self.app.redbeat_conf.key_prefix + self.name

    @property
    def score(self):
        if self.due_at is None:
            # Scores < zero are ignored on each tick.
            return -1
        return to_timestamp(self.due_at)

    @property
    def rank(self):
        return redis(self.app).zrank(self.app.redbeat_conf.schedule_key, self.key)

    def save(self):
        definition = {
            'name': self.name,
            'task': self.task,
            'args': self.args,
            'kwargs': self.kwargs,
            'options': self.options,
            'schedule': self.schedule,
            'enabled': self.enabled,
        }
        with redis(self.app).pipeline() as pipe:
            pipe.hset(self.key, 'definition', json.dumps(definition, cls=RedBeatJSONEncoder))
            pipe.zadd(self.app.redbeat_conf.schedule_key, self.score, self.key)
            pipe.execute()

        return self

    def delete(self):
        with redis(self.app).pipeline() as pipe:
            pipe.zrem(self.app.redbeat_conf.schedule_key, self.key)
            pipe.delete(self.key)
            pipe.execute()

    def _next_instance(self, last_run_at=None, only_update_last_run_at=False):
        entry = super(RedBeatSchedulerEntry, self)._next_instance(last_run_at=last_run_at)

        if only_update_last_run_at:
            # rollback the update to total_run_count
            entry.total_run_count = self.total_run_count

        meta = {
            'last_run_at': entry.last_run_at,
            'total_run_count': entry.total_run_count,
        }

        with redis(self.app).pipeline() as pipe:
            pipe.hset(self.key, 'meta', json.dumps(meta, cls=RedBeatJSONEncoder))
            pipe.zadd(self.app.redbeat_conf.schedule_key, entry.score, entry.key)
            pipe.execute()

        return entry
    __next__ = next = _next_instance

    def reschedule(self, last_run_at=None):
        self.last_run_at = last_run_at or self._default_now()
        meta = {
            'last_run_at': self.last_run_at,
        }
        with redis(self.app).pipeline() as pipe:
            pipe.hset(self.key, 'meta', json.dumps(meta, cls=RedBeatJSONEncoder))
            pipe.zadd(self.app.redbeat_conf.schedule_key, self.score, self.key)
            pipe.execute()

    def is_due(self):
        if not self.enabled:
            return False, 5.0  # 5 second delay for re-enable.

        return self.schedule.is_due(self.last_run_at or
                                    datetime(MINYEAR, 1, 1, tzinfo=self.schedule.tz))


class RedBeatScheduler(Scheduler):
    # how often should we sync in schedule information
    # from the backend redis database
    Entry = RedBeatSchedulerEntry

    lock = None

    #: The default lock timeout in seconds.
    lock_timeout = DEFAULT_MAX_INTERVAL * 5

    def __init__(self, app, lock_key=None, lock_timeout=None, **kwargs):
        ensure_conf(app)  # set app.redbeat_conf
        self.lock_key = lock_key or app.redbeat_conf.lock_key
        self.lock_timeout = (lock_timeout or
                             app.redbeat_conf.lock_timeout or
                             self.max_interval * 5 or
                             self.lock_timeout)
        super(RedBeatScheduler, self).__init__(app, **kwargs)

    def setup_schedule(self):
        # cleanup old static schedule entries
        client = redis(self.app)
        previous = set(key for key in client.smembers(self.app.redbeat_conf.statics_key))
        removed = previous.difference(self.app.redbeat_conf.schedule.keys())

        for name in removed:
            logger.debug("Removing old static schedule entry '%s'.", name)
            with client.pipeline() as pipe:
                RedBeatSchedulerEntry(name, app=self.app).delete()
                pipe.srem(self.app.redbeat_conf.statics_key, name)
                pipe.execute()

        # setup static schedule entries
        self.install_default_entries(self.app.redbeat_conf.schedule)
        if self.app.redbeat_conf.schedule:
            self.update_from_dict(self.app.redbeat_conf.schedule)

            # keep track of static schedule entries,
            # so we notice when any are removed at next startup
            client.sadd(self.app.redbeat_conf.statics_key,
                        *self.app.redbeat_conf.schedule.keys())

    def update_from_dict(self, dict_):
        for name, entry in dict_.items():
            try:
                entry = self._maybe_entry(name, entry)
            except Exception as exc:
                logger.error(ADD_ENTRY_ERROR, name, exc, entry)
                continue

            entry.save()  # store into redis
            logger.debug("Stored entry: %s", entry)

    def reserve(self, entry):
        new_entry = next(entry)
        return new_entry

    @property
    def schedule(self):
        logger.debug('Selecting tasks')

        max_due_at = to_timestamp(self.app.now())
        client = redis(self.app)

        with client.pipeline() as pipe:
            pipe.zrangebyscore(self.app.redbeat_conf.schedule_key, 0, max_due_at)

            # peek into the next tick to accuratly calculate sleep between ticks
            pipe.zrangebyscore(self.app.redbeat_conf.schedule_key,
                               '({}'.format(max_due_at),
                               max_due_at + self.max_interval,
                               start=0, num=1)
            due_tasks, maybe_due = pipe.execute()

        logger.info('Loading %d tasks', len(due_tasks) + len(maybe_due))
        d = {}
        for key in due_tasks + maybe_due:
            try:
                entry = self.Entry.from_key(key, app=self.app)
            except KeyError:
                logger.warning('failed to load %s, removing', key)
                client.zrem(self.app.redbeat_conf.schedule_key, key)
                continue

            d[entry.name] = entry

        return d

    def maybe_due(self, entry, **kwargs):
        is_due, next_time_to_run = entry.is_due()

        if is_due:
            logger.info('Scheduler: Sending due task %s (%s)', entry.name, entry.task)
            try:
                result = self.apply_async(entry, **kwargs)
            except Exception as exc:
                logger.exception('Message Error: %s', exc)
            else:
                logger.debug('%s sent. id->%s', entry.task, result.id)
        return next_time_to_run

    def tick(self, min=min, **kwargs):
        if self.lock:
            logger.debug('beat: Extending lock...')
            redis(self.app).pexpire(self.lock_key, int(self.lock_timeout * 1000))

        remaining_times = []
        try:
            for entry in values(self.schedule):
                next_time_to_run = self.maybe_due(entry, **self._maybe_due_kwargs)
                if next_time_to_run:
                    remaining_times.append(next_time_to_run)
        except RuntimeError:
            logger.debug('beat: RuntimeError', exc_info=True)

        return min(remaining_times + [self.max_interval])

    def close(self):
        if self.lock:
            logger.debug('beat: Releasing Lock')
            self.lock.release()
            self.lock = None
        super(RedBeatScheduler, self).close()

    @property
    def info(self):
        info = ['       . redis -> {}'.format(maybe_sanitize_url(self.app.redbeat_conf.redis_url))]
        if self.lock_key:
            info.append('       . lock -> `{}` {} ({}s)'.format(
                self.lock_key, humanize_seconds(self.lock_timeout), self.lock_timeout))
        return '\n'.join(info)

    @cached_property
    def _maybe_due_kwargs(self):
        """ handle rename of publisher to producer """
        if CELERY_4_OR_GREATER:
            return {'producer': self.producer}  # celery 4.x
        else:
            return {'publisher': self.publisher}  # celery 3.x


@beat_init.connect
def acquire_distributed_beat_lock(sender=None, **kwargs):
    scheduler = sender.scheduler
    if not scheduler.lock_key:
        return

    logger.debug('beat: Acquiring lock...')

    lock = redis(scheduler.app).lock(
        scheduler.lock_key,
        timeout=scheduler.lock_timeout,
        sleep=scheduler.max_interval,
    )
    lock.acquire()
    scheduler.lock = lock
