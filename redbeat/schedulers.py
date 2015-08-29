# Licensed under the Apache License, Version 2.0 (the 'License'); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
# Copyright 2014 Kong Luoxing, Copyright 2015 Marc Sibson


import datetime
import time

try:
    import simplejson as json
except ImportError:
    import json

from celery.beat import Scheduler, ScheduleEntry
from celery.utils.log import get_logger
from celery import current_app

from redis.client import StrictRedis

from decoder import RedBeatJSONEncoder, RedBeatJSONDecoder

# share with result backend
rdb = StrictRedis.from_url(current_app.conf.REDBEAT_REDIS_URL)

REDBEAT_SCHEDULE_KEY = current_app.conf.REDBEAT_KEY_PREFIX + ':schedule'

ADD_ENTRY_ERROR = """\

Couldn't add entry %r to redis schedule: %r. Contents: %r
"""

logger = get_logger(__name__)


def to_timestamp(dt):
    return time.mktime(dt.timetuple())


class RedBeatSchedulerEntry(ScheduleEntry):
    _meta = None

    def __init__(self, name=None, task=None, schedule=None, args=None, kwargs=None, enabled=True, **clsargs):
        super(RedBeatSchedulerEntry, self).__init__(name, task, schedule=schedule,
                                                    args=args, kwargs=kwargs, **clsargs)
        self.key = current_app.conf.REDBEAT_KEY_PREFIX + name
        self.enabled = enabled

    @staticmethod
    def load_definition(key):
        definition = rdb.hget(key, 'definition')
        if not definition:
            raise KeyError(key)

        return json.loads(definition, cls=RedBeatJSONDecoder)

    @staticmethod
    def load_meta(key):
        meta = rdb.hget(key, 'meta')
        if not meta:
            return {'last_run_at': datetime.datetime.min}

        return json.loads(meta, cls=RedBeatJSONDecoder)

    @staticmethod
    def from_key(key):
        definition = RedBeatSchedulerEntry.load_definition(key)
        meta = RedBeatSchedulerEntry.load_meta(key)
        definition.update(meta)

        return RedBeatSchedulerEntry(**definition)

    @property
    def due_at(self):
        delta = self.schedule.remaining_estimate(self.last_run_at)
        due_at = self.last_run_at + delta
        return to_timestamp(due_at)

    def save_definition(self):
        definition = {
            'name': self.name,
            'task': self.task,
            'args': self.args,
            'kwargs': self.kwargs,
            'options': self.options,
            'schedule': self.schedule,
            'enabled': self.enabled,
        }
        rdb.hset(self.key, 'definition', json.dumps(definition, cls=RedBeatJSONEncoder))

    def save_meta(self):
        meta = {
            'last_run_at': self.last_run_at,
            'total_run_count': self.total_run_count,
        }
        rdb.hset(self.key, 'meta', json.dumps(meta, cls=RedBeatJSONEncoder))

    def save(self):
        self.save_definition()
        RedBeatScheduler.update_schedule(self)

    def update_last_run_at(self, last_run_at=None):
        if last_run_at is None:
            last_run_at = self._default_now()

        self.last_run_at = last_run_at
        self.save_meta()
        RedBeatScheduler.update_schedule(self)

    def delete(self):
        rdb.zrem(REDBEAT_SCHEDULE_KEY, self.key)
        rdb.delete(self.key)

    def next(self):
        # TODO handle meta not loaded
        self.last_run_at = self._default_now()
        self.total_run_count += 1

        meta = {
            'last_run_at': self.last_run_at,
            'total_run_count': self.total_run_count,
        }
        rdb.hset(self.key, 'meta', json.dumps(meta, cls=RedBeatJSONEncoder))

        return self
    __next__ = next

    def is_due(self):
        if not self.enabled:
            return False, 5.0  # 5 second delay for re-enable.

        return super(RedBeatSchedulerEntry, self).is_due()


class RedBeatScheduler(Scheduler):
    # how often should we sync in schedule information
    # from the backend redis database
    Entry = RedBeatSchedulerEntry

    def setup_schedule(self):
        self.install_default_entries(self.app.conf.CELERYBEAT_SCHEDULE)
        self.update_from_dict(self.app.conf.CELERYBEAT_SCHEDULE)

    def update_from_dict(self, dict_):
        for name, entry in dict_.items():
            try:
                entry = self._maybe_entry(name, entry)
            except Exception as exc:
                logger.error(ADD_ENTRY_ERROR, name, exc, entry)
                continue

            entry.save()  # store into redis
            logger.debug(unicode(entry))

    def reserve(self, entry):
        new_entry = next(entry)
        self.update_schedule(new_entry)
        return new_entry

    @staticmethod
    def update_schedule(entry):
        rdb.zadd(REDBEAT_SCHEDULE_KEY, entry.due_at, entry.key)

    @property
    def schedule(self):
        # need to peek into the next tick to accurate calculate our sleep time
        max_due_at = to_timestamp(self.app.now() + datetime.timedelta(seconds=self.max_interval))
        due_tasks = rdb.zrangebyscore(REDBEAT_SCHEDULE_KEY, 0, max_due_at)
        d = {}
        for key in due_tasks:
            try:
                entry = self.Entry.from_key(key)
            except KeyError:
                logger.warning('failed to load %s, removing', key)
                rdb.zrem(REDBEAT_SCHEDULE_KEY, key)
                continue

            d[entry.name] = entry

        return d
