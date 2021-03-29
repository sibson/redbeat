from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import patch

from celery.utils.time import timezone

from redbeat.schedules import rrule


@patch.object(rrule, 'now', datetime.utcnow)
@patch.object(rrule, 'utc_enabled', True)
@patch.object(rrule, 'tz', timezone.utc)
class test_rrule_remaining_estimate(TestCase):
    def test_freq(self):
        r = rrule('MINUTELY', dtstart=datetime.utcnow() + timedelta(minutes=1))
        eta_from_now = r.remaining_estimate(datetime.utcnow())
        eta_after_one_minute = r.remaining_estimate(datetime.utcnow() + timedelta(minutes=1))
        self.assertTrue(eta_from_now.total_seconds() > 0)
        self.assertTrue(eta_after_one_minute.total_seconds() > 0)

    def test_freq__with_single_count(self):
        r = rrule('MINUTELY', dtstart=datetime.utcnow() + timedelta(minutes=1), count=1)
        eta_from_now = r.remaining_estimate(datetime.utcnow())
        eta_after_one_minute = r.remaining_estimate(datetime.utcnow() + timedelta(minutes=1))
        self.assertTrue(eta_from_now.total_seconds() > 0)
        self.assertEqual(eta_after_one_minute, None)

    def test_freq__with_multiple_count(self):
        r = rrule('MINUTELY', dtstart=datetime.utcnow() + timedelta(minutes=1), count=2)
        eta_from_now = r.remaining_estimate(datetime.utcnow())
        eta_after_one_minute = r.remaining_estimate(datetime.utcnow() + timedelta(minutes=1))
        eta_after_two_minutes = r.remaining_estimate(datetime.utcnow() + timedelta(minutes=2))
        self.assertTrue(eta_from_now.total_seconds() > 0)
        self.assertTrue(eta_after_one_minute.total_seconds() > 0)
        self.assertEqual(eta_after_two_minutes, None)


@patch.object(rrule, 'now', datetime.utcnow)
@patch.object(rrule, 'utc_enabled', True)
@patch.object(rrule, 'tz', timezone.utc)
class test_rrule_is_due(TestCase):
    def test_freq__starting_now(self):
        r = rrule('MINUTELY', dtstart=datetime.utcnow())
        # Assuming job was never run, i.e. last_run_at == epoch
        is_due, next = r.is_due(datetime(1970, 1, 1))
        self.assertTrue(is_due)
        self.assertTrue(next > 0)

    def test_freq__starts_after_one_minute(self):
        r = rrule('MINUTELY', dtstart=datetime.utcnow() + timedelta(minutes=1))
        is_due, next = r.is_due(datetime.utcnow())
        self.assertFalse(is_due)
        self.assertTrue(next > 0)

    def test_freq__with_single_count(self):
        r = rrule('MINUTELY', dtstart=datetime.utcnow(), count=1)
        # If job was never run, it should be due and have
        # no ETA for the following occurrence.
        is_due, next = r.is_due(datetime(1970, 1, 1))
        self.assertTrue(is_due)
        self.assertEqual(next, None)
        # It should not be due if it was already run once.
        is_due, next = r.is_due(datetime.utcnow())
        self.assertFalse(is_due)
        self.assertEqual(next, None)

    def test_freq__with_multiple_count(self):
        r = rrule('MINUTELY', dtstart=datetime.utcnow(), count=2)
        is_due, next = r.is_due(datetime(1970, 1, 1))
        self.assertTrue(is_due)
        self.assertTrue(next > 0)
        # There should still be one more occurrence remaining
        # if it was run once after dtstart.
        is_due, next = r.is_due(datetime.utcnow())
        self.assertFalse(is_due)
        self.assertTrue(next > 0)
        # There should be no more occurrences after one minute.
        is_due, next = r.is_due(datetime.utcnow() + timedelta(minutes=1))
        self.assertFalse(is_due)
        self.assertEqual(next, None)
