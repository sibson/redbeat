from datetime import datetime, timedelta

from celery.schedules import schedule
from celery.utils.timeutils import maybe_timedelta

from basecase import RedBeatCase
from redbeat import RedBeatScheduler


class mocked_schedule(schedule):

    def __init__(self, remaining):
        self._remaining = maybe_timedelta(remaining)
        self.run_every = timedelta(seconds=1)
        self.nowfun = datetime.utcnow

    def remaining_estimate(self, last_run_at):
        return self._remaining


due_now = mocked_schedule(0)


class test_RedBeatScheduler(RedBeatCase):

    def create_scheduler(self):
        return RedBeatScheduler(app=self.app)

    def test_empty_schedule(self):
        s = self.create_scheduler()

        self.assertEqual(s.schedule, {})
        sleep = s.tick()
        self.assertEqual(sleep, s.max_interval)

    def test_schedule_includes_current_and_next(self):
        s = self.create_scheduler()

        due = self.create_entry(name='due', s=due_now).save()
        up_next = self.create_entry(name='up_next', s=mocked_schedule(1)).save()
        up_next2 = self.create_entry(name='up_next2', s=mocked_schedule(1)).save()
        way_out = self.create_entry(name='way_out', s=mocked_schedule(s.max_interval * 10)).save()

        schedule = s.schedule
        self.assertEqual(len(schedule), 2)

        self.assertIn(due.name, schedule)
        self.assertEqual(due.key, schedule[due.name].key)

        self.assertIn(up_next.name, schedule)
        self.assertEqual(up_next.key, schedule[up_next.name].key)

        self.assertNotIn(up_next2.name, schedule)
        self.assertNotIn(way_out.name, schedule)

    def test_old_static_entries_are_removed(self):
        conf = self.app.conf
        conf.CELERYBEAT_SCHEDULE = {
            'test': {
                'task': 'test',
                'schedule': mocked_schedule(42)
            }
        }
        s = self.create_scheduler()
        redis = self.app.redbeat_redis

        self.assertIn('test', s.schedule)
        self.assertIn('test', redis.smembers(conf.REDBEAT_STATICS_KEY))

        conf.CELERYBEAT_SCHEDULE = {}
        s.setup_schedule()

        self.assertNotIn('test', s.schedule)
        self.assertNotIn('test', redis.smembers(conf.REDBEAT_STATICS_KEY))
