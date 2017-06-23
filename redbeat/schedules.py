import celery
from dateutil.rrule import rrule as dateutil_rrule
try:  # celery 4.x
    from celery.schedules import BaseSchedule as schedule
    from celery.utils.time import (
        localize,
        timezone
    )
except ImportError:  # celery 3.x
    from celery.schedules import schedule
    from celery.utils.timeutils import (
        localize,
        timezone
    )


class rrule(schedule):
    RRULE_REPR = """\
    <rrule: {0._freq} {0._interval}>\
    """

    def __init__(self, freq, dtstart=None,
                 interval=1, wkst=None, count=None, until=None, bysetpos=None,
                 bymonth=None, bymonthday=None, byyearday=None, byeaster=None,
                 byweekno=None, byweekday=None,
                 byhour=None, byminute=None, bysecond=None,
                 **kwargs):
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
        last_run_at = self.maybe_make_aware(last_run_at)
        last_run_at_utc = localize(last_run_at, timezone.utc)
        last_run_at_utc_naive = last_run_at_utc.replace(tzinfo=None)
        next_run_utc = self.rrule.after(last_run_at_utc_naive)
        if next_run_utc:
            next = self.maybe_make_aware(next_run_utc)
            now = self.maybe_make_aware(self.now())
            delta = next - now
            return delta
        return None

    def is_due(self, last_run_at):
        rem_delta = self.remaining_estimate(last_run_at)
        if rem_delta:
            rem = max(rem_delta.total_seconds(), 0)
            due = rem == 0
            if due:
                rem_delta = self.remaining_estimate(self.now())
                if rem_delta:
                    rem = max(rem_delta.total_seconds(), 0)
                else:
                    rem = 0
            return celery.schedules.schedstate(due, rem)
        return celery.schedules.schedstate(False, None)

    def __repr__(self):
        return self.RRULE_REPR.format(self)

    def __reduce__(self):
        return (self.__class__, (self.rrule), None)
