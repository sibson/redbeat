import json
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from celery.schedules import crontab, schedule
from dateutil import rrule as dateutil_rrule

from redbeat.decoder import RedBeatJSONDecoder, RedBeatJSONEncoder
from redbeat.schedules import rrule

try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo


class JSONTestCase(TestCase):
    def dumps(self, d):
        return json.dumps(d, cls=RedBeatJSONEncoder)

    def loads(self, d):
        return json.loads(d, cls=RedBeatJSONDecoder)

    def datetime_as_dict(self, **kwargs):
        d = {
            'year': 2015,
            'month': 12,
            'day': 30,
            'hour': 12,
            'minute': 59,
            'second': 22,
            'microsecond': 333,
        }
        d.update(kwargs)
        return d

    def now(self, **kwargs):
        d = self.datetime_as_dict(**kwargs)
        dt = datetime(d.pop('year'), d.pop('month'), d.pop('day'), **d)
        return dt

    def schedule(self, **kwargs):
        d = {
            '__type__': 'interval',
            'every': 60.0,
            'relative': False,
        }
        d.update(kwargs)
        return d

    def crontab(self, **kwargs):
        d = {
            '__type__': 'crontab',
            'minute': '*',
            'hour': '*',
            'day_of_week': '*',
            'day_of_month': '*',
            'month_of_year': '*',
        }
        d.update(kwargs)
        return d

    def rrule(self, **kwargs):
        d = {
            '__type__': 'rrule',
            'freq': 5,
            'dtstart': 1451480362,
            'dtstart_tz': 0,
            'interval': 1,
            'wkst': None,
            'count': 1,
            'until': 1451566762,
            'until_tz': 0,
            'bysetpos': None,
            'bymonth': None,
            'bymonthday': None,
            'byyearday': None,
            'byeaster': None,
            'byweekno': None,
            'byweekday': None,
            'byhour': None,
            'byminute': None,
            'bysecond': None,
        }
        d.update(kwargs)
        return d

    def weekday(self, **kwargs):
        d = {
            '__type__': 'weekday',
            'wkday': 5,
        }
        d.update(kwargs)
        return d


class RedBeatJSONEncoderTestCase(JSONTestCase):
    def test_datetime_no_tz(self):
        dt = self.now()
        result = self.dumps(dt)

        expected = self.datetime_as_dict(__type__='datetime', timezone='UTC')
        self.assertEqual(json.loads(result), expected)

    def test_datetime_with_tz(self):
        dt = self.now(tzinfo=zoneinfo.ZoneInfo('Asia/Shanghai'))
        result = self.dumps(dt)

        expected = self.datetime_as_dict(timezone='Asia/Shanghai', __type__='datetime')
        self.assertEqual(json.loads(result), expected)

    def test_datetime_with_fixedoffset(self):
        dt = self.now(tzinfo=timezone(timedelta(hours=4)))
        result = self.dumps(dt)

        expected = self.datetime_as_dict(timezone=4 * 60 * 60.0)
        expected['__type__'] = 'datetime'
        self.assertEqual(json.loads(result), expected)

    def test_schedule(self):
        s = schedule(run_every=60.0)
        result = self.dumps(s)
        self.assertEqual(result, json.dumps(self.schedule(every=60.0)))

    def test_crontab(self):
        c = crontab()
        result = self.dumps(c)
        self.assertEqual(result, json.dumps(self.crontab()))

    def test_rrule(self):
        r = rrule(
            'MINUTELY',
            dtstart=datetime(2015, 12, 30, 12, 59, 22, tzinfo=timezone.utc),
            until=datetime(2015, 12, 31, 12, 59, 22, tzinfo=timezone.utc),
            count=1,
        )
        result = self.dumps(r)
        self.assertEqual(json.loads(result), self.rrule())

    def test_rrule_timezone(self):
        tz = zoneinfo.ZoneInfo('US/Eastern')

        start1 = datetime(2015, 12, 30, 12, 59, 22, tzinfo=timezone.utc)
        start2 = start1.astimezone(tz)

        r1 = rrule('MINUTELY', dtstart=start1, count=1)
        r2 = rrule('MINUTELY', dtstart=start2, count=1)

        r1_json = self.dumps(r1)
        r2_json = self.dumps(r2)

        r1_parsed = self.loads(r1_json)
        self.assertEqual(r1_parsed.dtstart.utcoffset(), r1.dtstart.utcoffset())

        r2_parsed = self.loads(r2_json)
        self.assertEqual(r2_parsed.dtstart.utcoffset(), r2.dtstart.utcoffset())

        self.assertEqual(r1_parsed.dtstart, r2_parsed.dtstart)
        self.assertNotEqual(r1_parsed.dtstart.utcoffset(), r2_parsed.dtstart.utcoffset())

    def test_weekday(self):
        w = dateutil_rrule.weekday(5)
        result = self.dumps(w)
        self.assertEqual(json.loads(result), self.weekday())

    def test_weekday_in_rrule(self):
        r = rrule(
            dateutil_rrule.WEEKLY,
            dtstart=datetime(2015, 12, 30, 12, 59, 22, tzinfo=timezone.utc),
            until=datetime(2015, 12, 31, 12, 59, 22, tzinfo=timezone.utc),
            byweekday=(dateutil_rrule.MO, dateutil_rrule.WE, dateutil_rrule.FR),
        )
        result = self.dumps(r)
        self.assertEqual(
            json.loads(result),
            {
                '__type__': 'rrule',
                'freq': 2,
                'dtstart': 1451480362,
                'dtstart_tz': 0,
                'interval': 1,
                'wkst': None,
                'count': None,
                'until': 1451566762,
                'until_tz': 0,
                'bysetpos': None,
                'bymonth': None,
                'bymonthday': None,
                'byyearday': None,
                'byeaster': None,
                'byweekno': None,
                'byweekday': [
                    {'__type__': 'weekday', 'wkday': 0},
                    {'__type__': 'weekday', 'wkday': 2},
                    {'__type__': 'weekday', 'wkday': 4},
                ],
                'byhour': None,
                'byminute': None,
                'bysecond': None,
            },
        )


class RedBeatJSONDecoderTestCase(JSONTestCase):
    def test_datetime_no_timezone(self):
        d = self.datetime_as_dict(__type__='datetime')
        result = self.loads(json.dumps(d))
        d.pop('__type__')
        self.assertEqual(result, datetime(tzinfo=timezone.utc, **d))

    def test_datetime_with_timezone(self):
        d = self.datetime_as_dict(__type__='datetime', timezone='Asia/Shanghai')
        result = self.loads(json.dumps(d))
        d.pop('__type__')
        d.pop('timezone')
        self.assertEqual(result, datetime(tzinfo=zoneinfo.ZoneInfo('Asia/Shanghai'), **d))

    def test_datetime_with_fixed_offset(self):
        d = self.datetime_as_dict(__type__='datetime', timezone=5 * 60 * 60)
        result = self.loads(json.dumps(d))
        d.pop('__type__')
        d.pop('timezone')
        self.assertEqual(result, datetime(tzinfo=timezone(timedelta(hours=5)), **d))

    def test_schedule(self):
        d = self.schedule()

        result = self.loads(json.dumps(d))
        self.assertEqual(result, schedule(run_every=60))

    def test_crontab(self):
        d = self.crontab()

        result = self.loads(json.dumps(d))
        self.assertEqual(result, crontab())

    def test_rrule(self):
        d = self.rrule()

        result = self.loads(json.dumps(d))
        self.assertEqual(
            result,
            rrule(
                'MINUTELY', dtstart=datetime(2015, 12, 30, 12, 59, 22, tzinfo=timezone.utc), count=1
            ),
        )

    def test_weekday(self):
        d = self.weekday()

        result = self.loads(json.dumps(d))
        self.assertEqual(result, dateutil_rrule.weekday(5))
