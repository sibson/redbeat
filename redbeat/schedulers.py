# Licensed under the Apache License, Version 2.0 (the 'License'); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
# Copyright 2015 Marc Sibson

from __future__ import absolute_import

from datetime import datetime, MINYEAR
import time

try:
    import simplejson as json
except ImportError:
    import json

from celery.beat import Scheduler, ScheduleEntry
from celery.utils.log import get_logger
from celery.signals import beat_init
try:  # celery 3.x
    from celery.utils.timeutils import humanize_seconds
    from kombu.utils import cached_property
except ImportError:  # celery 4.x
    from celery.utils.time import humanize_seconds
    from kombu.utils.objects import cached_property
from celery.app import app_or_default
from celery.five import values

from redis.client import StrictRedis

from .decoder import RedBeatJSONEncoder, RedBeatJSONDecoder


def add_defaults(app=None):
    app = app_or_default(app)

    app.add_defaults({
        'REDBEAT_REDIS_URL': app.conf.get('REDBEAT_REDIS_URL', app.conf['BROKER_URL']),
        'REDBEAT_KEY_PREFIX': app.conf.get('REDBEAT_KEY_PREFIX', 'redbeat:'),
        'REDBEAT_SCHEDULE_KEY': app.conf.get('REDBEAT_KEY_PREFIX', 'redbeat:') + ':schedule',
        'REDBEAT_STATICS_KEY': app.conf.get('REDBEAT_KEY_PREFIX', 'redbeat:') + ':statics',
        'REDBEAT_LOCK_KEY': app.conf.get('REDBEAT_KEY_PREFIX', 'redbeat:') + ':lock',
        'REDBEAT_LOCK_TIMEOUT': app.conf.CELERYBEAT_MAX_LOOP_INTERVAL * 5,
    })


def redis(app=None):
    app = app_or_default(app)

    if not hasattr(app, 'redbeat_redis') or app.redbeat_redis is None:
        app.redbeat_redis = StrictRedis.from_url(app.conf.REDBEAT_REDIS_URL,
                                                 decode_responses=True)

    return app.redbeat_redis


ADD_ENTRY_ERROR = """\

Couldn't add entry %r to redis schedule: %r. Contents: %r
"""

logger = get_logger(__name__)


def to_timestamp(dt):
    return time.mktime(dt.timetuple())


def from_timestamp(ts):
    return datetime.fromtimestamp(ts)


class RedBeatSchedulerEntry(ScheduleEntry):
    _meta = None

    def __init__(self, name=None, task=None, schedule=None, args=None, kwargs=None, enabled=True, **clsargs):
        super(RedBeatSchedulerEntry, self).__init__(name=name, task=task, schedule=schedule,
                                                    args=args, kwargs=kwargs, **clsargs)
        self.enabled = enabled

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

        # overdue => due now
        if delta.total_seconds() < 0:
            return self._default_now()

        return self.last_run_at + delta

    @property
    def key(self):
        return app_or_default(self.app).conf['REDBEAT_KEY_PREFIX'] + self.name

    @property
    def score(self):
        return to_timestamp(self.due_at)

    @property
    def rank(self):
        return redis(self.app).zrank(self.app.conf.REDBEAT_SCHEDULE_KEY, self.key)

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
            pipe.zadd(self.app.conf.REDBEAT_SCHEDULE_KEY, self.score, self.key)
            pipe.execute()

        return self

    def delete(self):
        with redis(self.app).pipeline() as pipe:
            pipe.zrem(self.app.conf.REDBEAT_SCHEDULE_KEY, self.key)
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
            pipe.zadd(self.app.conf.REDBEAT_SCHEDULE_KEY, entry.score, entry.key)
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
            pipe.zadd(self.app.conf.REDBEAT_SCHEDULE_KEY, self.score, self.key)
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

    def __init__(self, app, **kwargs):
        add_defaults(app)
        self.lock_key = kwargs.pop('lock_key', app.conf.REDBEAT_LOCK_KEY)
        self.lock_timeout = kwargs.pop('lock_timeout', app.conf.REDBEAT_LOCK_TIMEOUT)
        super(RedBeatScheduler, self).__init__(app, **kwargs)

    def setup_schedule(self):
        # cleanup old static schedule entries
        client = redis(self.app)
        previous = set(key for key in client.smembers(self.app.conf.REDBEAT_STATICS_KEY))
        removed = previous.difference(self.app.conf.CELERYBEAT_SCHEDULE.keys())

        for name in removed:
            logger.debug("Removing old static schedule entry '%s'.", name)
            with client.pipeline() as pipe:
                RedBeatSchedulerEntry(name, app=self.app).delete()
                pipe.srem(self.app.conf.REDBEAT_STATICS_KEY, name)
                pipe.execute()

        # setup static schedule entries
        self.install_default_entries(self.app.conf.CELERYBEAT_SCHEDULE)
        if self.app.conf.CELERYBEAT_SCHEDULE:
            self.update_from_dict(self.app.conf.CELERYBEAT_SCHEDULE)

            # keep track of static schedule entries,
            # so we notice when any are removed at next startup
            client.sadd(self.app.conf.REDBEAT_STATICS_KEY,
                        *self.app.conf.CELERYBEAT_SCHEDULE.keys())

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
            pipe.zrangebyscore(self.app.conf.REDBEAT_SCHEDULE_KEY, 0, max_due_at)

            # peek into the next tick to accuratly calculate sleep between ticks
            pipe.zrangebyscore(self.app.conf.REDBEAT_SCHEDULE_KEY,
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
                client.zrem(self.app.conf.REDBEAT_SCHEDULE_KEY, key)
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
        info = ['       . redis -> {}'.format(self.app.conf.REDBEAT_REDIS_URL)]
        if self.lock_key:
            info.append('       . lock -> `{}` {} ({}s)'.format(
                self.lock_key, humanize_seconds(self.lock_timeout), self.lock_timeout))
        return '\n'.join(info)

    @cached_property
    def _maybe_due_kwargs(self):
        """ handle rename of publisher to producer """
        try:
            return {'producer': self.producer}  # celery 4.x
        except AttributeError:
            return {'publisher': self.publisher}  # celery 3.x

@beat_init.connect
def acquire_distributed_beat_lock(sender=None, **kwargs):
    scheduler = sender.scheduler
    if not scheduler.lock_key:
        return

    logger.debug('beat: Acquiring lock...')

    lock = redis(scheduler.app).lock(
            scheduler.lock_key, timeout=scheduler.lock_timeout, sleep=scheduler.max_interval)
    lock.acquire()
    scheduler.lock = lock
