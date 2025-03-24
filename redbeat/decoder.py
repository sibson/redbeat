import calendar
import json
from datetime import datetime, timedelta, timezone

from celery.schedules import crontab, schedule
from dateutil.rrule import weekday

try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo

from .schedules import rrule


def to_timestamp(dt):
    """convert local tz aware datetime to seconds since the epoch"""
    return calendar.timegm(dt.utctimetuple())


def get_utcoffset_minutes(dt):
    """calculates timezone utc offset, returns minutes relative to utc"""
    utcoffset = dt.utcoffset()

    # Python 3: utcoffset / timedelta(minutes=1)
    return utcoffset.total_seconds() / 60 if utcoffset else 0


def from_timestamp(seconds, tz_minutes=0):
    """convert seconds since the epoch to an UTC aware datetime"""
    tz = timezone(timedelta(minutes=tz_minutes)) if tz_minutes else timezone.utc
    return datetime.fromtimestamp(seconds, tz=tz)


class RedBeatJSONDecoder(json.JSONDecoder):
    def __init__(self, *args, **kargs):
        super().__init__(object_hook=self.dict_to_object, *args, **kargs)

    def dict_to_object(self, d):
        if '__type__' not in d:
            return d

        objtype = d.pop('__type__')

        if objtype == 'datetime':
            zone = d.pop('timezone', 'UTC')
            try:
                tzinfo = timezone(timedelta(minutes=(zone / 60)))
            except TypeError:
                tzinfo = zoneinfo.ZoneInfo(zone)
            return datetime(tzinfo=tzinfo, **d)

        if objtype == 'interval':
            return schedule(run_every=d['every'], relative=d['relative'])

        if objtype == 'crontab':
            return crontab(**d)

        if objtype == 'weekday':
            return weekday(**d)

        if objtype == 'rrule':
            # Decode timestamp values into datetime objects
            for key, tz_key in [('dtstart', 'dtstart_tz'), ('until', 'until_tz')]:
                timestamp = d.get(key)
                tz_minutes = d.pop(tz_key, 0)
                if timestamp is not None:
                    d[key] = from_timestamp(timestamp, tz_minutes)
            return rrule(**d)

        d['__type__'] = objtype

        return d


class RedBeatJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            if obj.tzinfo is None:
                timezone = 'UTC'
            elif hasattr(obj.tzinfo, 'key'):
                timezone = obj.tzinfo.key
            else:
                timezone = obj.utcoffset().total_seconds()

            return {
                '__type__': 'datetime',
                'year': obj.year,
                'month': obj.month,
                'day': obj.day,
                'hour': obj.hour,
                'minute': obj.minute,
                'second': obj.second,
                'microsecond': obj.microsecond,
                'timezone': timezone,
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
            res = {
                '__type__': 'rrule',
                'freq': obj.freq,
                'interval': obj.interval,
                'wkst': obj.wkst,
                'count': obj.count,
                'bysetpos': obj.bysetpos,
                'bymonth': obj.bymonth,
                'bymonthday': obj.bymonthday,
                'byyearday': obj.byyearday,
                'byeaster': obj.byeaster,
                'byweekno': obj.byweekno,
                'byweekday': obj.byweekday,
                'byhour': obj.byhour,
                'byminute': obj.byminute,
                'bysecond': obj.bysecond,
            }

            # Convert datetime objects to timestamps
            if obj.dtstart:
                res['dtstart'] = to_timestamp(obj.dtstart)
                res['dtstart_tz'] = get_utcoffset_minutes(obj.dtstart)

            if obj.until:
                res['until'] = to_timestamp(obj.until)
                res['until_tz'] = get_utcoffset_minutes(obj.until)

            return res

        if isinstance(obj, weekday):
            return {'__type__': 'weekday', 'wkday': obj.weekday}

        if isinstance(obj, schedule):
            return {
                '__type__': 'interval',
                'every': obj.run_every.total_seconds(),
                'relative': bool(obj.relative),
            }

        return super().default(obj)
