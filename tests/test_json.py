from datetime import datetime
import json
from unittest import TestCase

from celery.schedules import schedule, crontab

from redbeat.decoder import RedBeatJSONDecoder, RedBeatJSONEncoder


class JSONTestCase(TestCase):

    def dumps(self, d):
        return json.dumps(d, cls=RedBeatJSONEncoder)

    def loads(self, d):
        return json.loads(d, cls=RedBeatJSONDecoder)

    def datetime(self, **kwargs):
        d = {
            '__type__': 'datetime',
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


class RedBeatJSONEncoderTestCase(JSONTestCase):

    def test_datetime(self):
        dt = datetime.now()
        result = self.dumps(dt)

        expected = self.datetime()
        for key in (k for k in expected if hasattr(dt, k)):
            expected[key] = getattr(dt, key)

        self.assertEqual(result, json.dumps(expected))

    def test_schedule(self):
        s = schedule(run_every=60.0)
        result = self.dumps(s)
        self.assertEqual(result, json.dumps(self.schedule(every=60.0)))

    def test_crontab(self):
        c = crontab()
        result = self.dumps(c)
        self.assertEqual(result, json.dumps(self.crontab()))


class RedBeatJSONDecoderTestCase(JSONTestCase):

    def test_datetime(self):
        d = self.datetime()

        result = self.loads(json.dumps(d))

        d.pop('__type__')
        self.assertEqual(result, datetime(**d))

    def test_schedule(self):
        d = self.schedule()

        result = self.loads(json.dumps(d))

        d.pop('__type__')
        self.assertEqual(result, schedule(run_every=60))

    def test_crontab(self):
        d = self.crontab()

        result = self.loads(json.dumps(d))

        d.pop('__type__')
        self.assertEqual(result, crontab())
