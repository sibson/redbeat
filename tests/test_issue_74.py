import unittest
from datetime import datetime, timedelta, timezone

from redbeat.schedules import rrule
from tests.basecase import RedBeatCase

CREATED_AT = datetime(2017, 12, 9, 21, 19, 58, tzinfo=timezone.utc)


class test_Issue_74(RedBeatCase):
    """An rrule entry skips the occurrence at dtstart, delaying the first run.

    https://github.com/sibson/redbeat/issues/74

    An rrule built without an explicit dtstart defaults it to the creation
    time (redbeat/schedules.py:53), and celery's ScheduleEntry defaults
    last_run_at to the same instant. remaining_estimate then asks
    dateutil for rrule.after(last_run_at) (redbeat/schedules.py:93), which
    is exclusive, so the occurrence sitting exactly on dtstart is passed
    over.

    Expected: due at dtstart, the rrule's own first occurrence.
    Actual:   due one full interval later.

    TRIAGE ARTIFACT -- this file is temporary. When the fix lands, move this
    test into tests/test_schedules.py, drop the expectedFailure marker,
    rename it for the behaviour it checks rather than the issue number, and
    delete this file.
    """

    @unittest.expectedFailure
    def test_first_occurrence_is_due_at_dtstart(self):
        schedule = rrule('MINUTELY', interval=3, count=4, nowfun=lambda: CREATED_AT)
        self.assertEqual(schedule.dtstart, CREATED_AT)

        entry = self.create_entry(s=schedule)

        self.assertEqual(entry.due_at, CREATED_AT)

    def test_first_occurrence_is_delayed_by_one_interval(self):
        """Pin the current behaviour, so the fix has to change this line too."""
        schedule = rrule('MINUTELY', interval=3, count=4, nowfun=lambda: CREATED_AT)
        entry = self.create_entry(s=schedule)

        self.assertEqual(entry.due_at, CREATED_AT + timedelta(minutes=3))
