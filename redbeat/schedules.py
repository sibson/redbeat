import celery
from dateutil.rrule import (
    rrule as dateutil_rrule,
    YEARLY,
    MONTHLY,
    WEEKLY,
    DAILY,
    HOURLY,
    MINUTELY,
    SECONDLY
)
try:  # celery 4.x
    from celery.schedules import BaseSchedule as schedule
except ImportError:  # celery 3.x
    from celery.schedules import schedule


class rrule(schedule):
    RRULE_REPR = (
        '<rrule: freq: {0.freq}, dtstart: {0.dtstart}, interval: {0.interval}, '
        'wkst: {0.wkst}, count: {0.count}, until: {0.until}, bysetpos: {0.bysetpos}, '
        'bymonth: {0.bymonth}, bymonthday: {0.bymonthday}, byyearday: {0.byyearday}, '
        'byeaster: {0.byeaster}, byweekno: {0.byweekno}, byweekday: {0.byweekday}, '
        'byhour: {0.byhour}, byminute: {0.byminute}, bysecond: {0.bysecond}>'
    )

    FREQ_MAP = {
        'YEARLY': YEARLY,
        'MONTHLY': MONTHLY,
        'WEEKLY': WEEKLY,
        'DAILY': DAILY,
        'HOURLY': HOURLY,
        'MINUTELY': MINUTELY,
        'SECONDLY': SECONDLY
    }

    def __init__(self, freq, dtstart=None,
                 interval=1, wkst=None, count=None, until=None, bysetpos=None,
                 bymonth=None, bymonthday=None, byyearday=None, byeaster=None,
                 byweekno=None, byweekday=None,
                 byhour=None, byminute=None, bysecond=None,
                 **kwargs):
        if type(freq) == str:
            freq_str = freq.upper()
            assert freq_str in rrule.FREQ_MAP
            freq = rrule.FREQ_MAP[freq_str]

        self.freq = freq
        self.dtstart = dtstart
        self.interval = interval
        self.wkst = wkst
        self.count = count
        self.until = until
        self.bysetpos = bysetpos
        self.bymonth = bymonth
        self.bymonthday = bymonthday
        self.byyearday = byyearday
        self.byeaster = byeaster
        self.byweekno = byweekno
        self.byweekday = byweekday
        self.byhour = byhour
        self.byminute = byminute
        self.bysecond = bysecond
        self.rrule = dateutil_rrule(freq, dtstart, interval, wkst, count, until,
                                    bysetpos, bymonth, bymonthday, byyearday, byeaster,
                                    byweekno, byweekday, byhour, byminute, bysecond)
        super(rrule, self).__init__(**kwargs)

    def remaining_estimate(self, last_run_at):
        # This expects last_run_at to be in UTC time.
        next_run_utc = self.rrule.after(last_run_at)
        if next_run_utc:
            now_utc = self.now()
            delta = next_run_utc - now_utc
            return delta
        return None

    def is_due(self, last_run_at):
        rem_delta = self.remaining_estimate(last_run_at)
        if rem_delta is not None:
            rem = max(rem_delta.total_seconds(), 0)
            due = rem == 0
            if due:
                rem_delta = self.remaining_estimate(self.now())
                if rem_delta is not None:
                    rem = max(rem_delta.total_seconds(), 0)
                else:
                    rem = None
            return celery.schedules.schedstate(due, rem)
        return celery.schedules.schedstate(False, None)

    def __repr__(self):
        return self.RRULE_REPR.format(self)

    def __reduce__(self):
        return (self.__class__, (self.rrule), None)
