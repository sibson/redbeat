# coding: utf-8

from datetime import datetime

try:
    import simplejson as json
except ImportError:
    import json

from celery.schedules import schedule, crontab


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

        return super(RedBeatJSONEncoder, self).default(obj)
