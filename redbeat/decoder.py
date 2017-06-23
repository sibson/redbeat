# coding: utf-8

import time
from datetime import datetime

try:
    import simplejson as json
except ImportError:
    import json

from celery.schedules import schedule, crontab
from .schedules import rrule


class RedBeatJSONDecoder(json.JSONDecoder):
    def __init__(self, *args, **kargs):
        super(RedBeatJSONDecoder, self).__init__(object_hook=self.dict_to_object, *args, **kargs)

    def dict_to_object(self, d):
        if '__type__' not in d:
            return d

        objtype = d.pop('__type__')

        if objtype == 'datetime':
            return datetime(**d)

        if objtype == 'interval':
            return schedule(run_every=d['every'], relative=d['relative'])

        if objtype == 'crontab':
            return crontab(**d)

        if objtype == 'rrule':
            rrule_dict = d
            # Decode timestamp values into datetime objects
            for key in ['dtstart', 'until']:
                if rrule_dict[key] is not None:
                    rrule_dict[key] = datetime.fromtimestamp(rrule_dict[key])
            return rrule(**rrule_dict)

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
        if isinstance(obj, schedule):
            return {
                '__type__': 'interval',
                'every': obj.run_every.total_seconds(),
                'relative': bool(obj.relative),
            }
        if isinstance(obj, rrule):
            # Convert datetime objects to timestamps
            dtstart_ts = time.mktime(obj.dtstart.timetuple()) \
                if obj.dtstart else None
            until_ts = time.mktime(obj.until.timetuple()) \
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
        return super(RedBeatJSONEncoder, self).default(obj)
