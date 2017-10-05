# coding: utf-8

import calendar
from datetime import datetime

try:
    import simplejson as json
except ImportError:
    import json

try:  # celery 3.x
    from celery.utils.timeutils import timezone
except ImportError:  # celery 4.x
    from celery.utils.time import timezone

from celery.schedules import schedule, crontab
from .schedules import rrule


def to_timestamp(dt):
    """ convert UTC datetime to seconds since the epoch """
    return calendar.timegm(dt.timetuple())


def from_timestamp(seconds):
    """ convert seconds since the epoch to an UTC aware datetime """
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


class RedBeatJSONDecoder(json.JSONDecoder):
    def __init__(self, *args, **kargs):
        super(RedBeatJSONDecoder, self).__init__(object_hook=self.dict_to_object, *args, **kargs)

    def dict_to_object(self, d):
        if '__type__' not in d:
            return d

        objtype = d.pop('__type__')

        if objtype == 'datetime':
            return datetime(tzinfo=timezone.utc, **d)

        if objtype == 'interval':
            return schedule(run_every=d['every'], relative=d['relative'])

        if objtype == 'crontab':
            return crontab(**d)

        if objtype == 'rrule':
            # Decode timestamp values into datetime objects
            for key in ['dtstart', 'until']:
                if d[key] is not None:
                    d[key] = from_timestamp(d[key])
            return rrule(**d)

        d['__type__'] = objtype

        return d


class RedBeatJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return {
                '__type__': 'datetime',
                'year': obj.year,
                'month': obj.month,
                'day': obj.day,
                'hour': obj.hour,
                'minute': obj.minute,
                'second': obj.second,
                'microsecond': obj.microsecond,
            }
        if isinstance(obj, crontab):
            return {
                '__type__': 'crontab',
                'minute': obj._orig_minute,
                'hour': obj._orig_hour,
                'day_of_week': obj._orig_day_of_week,
                'day_of_month': obj._orig_day_of_month,
                'month_of_year': obj._orig_month_of_year,
            }
        if isinstance(obj, rrule):
            # Convert datetime objects to timestamps
            dtstart_ts = to_timestamp(obj.dtstart) \
                if obj.dtstart else None
            until_ts = to_timestamp(obj.until) \
                if obj.until else None

            return {
                '__type__': 'rrule',
                'freq': obj.freq,
                'dtstart': dtstart_ts,
                'interval': obj.interval,
                'wkst': obj.wkst,
                'count': obj.count,
                'until': until_ts,
                'bysetpos': obj.bysetpos,
                'bymonth': obj.bymonth,
                'bymonthday': obj.bymonthday,
                'byyearday': obj.byyearday,
                'byeaster': obj.byeaster,
                'byweekno': obj.byweekno,
                'byweekday': obj.byweekday,
                'byhour': obj.byhour,
                'byminute': obj.byminute,
                'bysecond': obj.bysecond
            }
        if isinstance(obj, schedule):
            return {
                '__type__': 'interval',
                'every': obj.run_every.total_seconds(),
                'relative': bool(obj.relative),
            }
        return super(RedBeatJSONEncoder, self).default(obj)
