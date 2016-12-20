from datetime import datetime, timedelta

from celery.schedules import schedule
from celery.utils.timeutils import maybe_timedelta

from mock import patch, ANY

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
due_next = mocked_schedule(1)


class RedBeatSchedulerTestBase(RedBeatCase):
    def setUp(self):
        super(RedBeatSchedulerTestBase, self).setUp()
        self.s = RedBeatScheduler(app=self.app)
        self.due_later = mocked_schedule(self.s.max_interval * 10)
        self.send_task = patch.object(self.s, 'send_task')
        self.send_task.start()

    def tearDown(self):
        self.send_task.stop()


class test_RedBeatScheduler_schedule(RedBeatSchedulerTestBase):

    def test_empty_schedule(self):
        self.assertEqual(self.s.schedule, {})

    def test_schedule_includes_current_and_next(self):
        due = self.create_entry(name='due', s=due_now).save()
        up_next = self.create_entry(name='up_next', s=due_next).save()
        up_next2 = self.create_entry(name='up_next2', s=due_next).save()
        later = self.create_entry(name='later', s=self.due_later).save()

        schedule = self.s.schedule

        self.assertEqual(len(schedule), 2)

        self.assertIn(due.name, schedule)
        self.assertEqual(due.key, schedule[due.name].key)

        self.assertIn(up_next.name, schedule)
        self.assertEqual(up_next.key, schedule[up_next.name].key)

        self.assertNotIn(up_next2.name, schedule)
        self.assertNotIn(later.name, schedule)


class test_RedBeatScheduler_tick(RedBeatSchedulerTestBase):

    def test_empty(self):
        with patch.object(self.s, 'send_task') as send_task:
            sleep = self.s.tick()
            self.assertFalse(send_task.called)

        self.assertEqual(sleep, self.s.max_interval)

    def test_due_next_never_run(self):
        e = self.create_entry(name='next', s=due_next).save()

        with patch.object(self.s, 'send_task') as send_task:
            sleep = self.s.tick()
            # debateable if we should be calling the task that isn't due quite yet
            #self.assertFalse(send_task.called)
            send_task.assert_called_with(e.task, e.args, e.kwargs, publisher=ANY, **e.options)

        self.assertEqual(sleep, 1.0)

    def test_due_next_just_ran(self):
        e = self.create_entry(name='next', s=due_next)
        e.save().reschedule()

        with patch.object(self.s, 'send_task') as send_task:
            sleep = self.s.tick()
            self.assertFalse(send_task.called)
        self.assertLess(0.8, sleep)
        self.assertLess(sleep, 1.0)

    def test_due_later_never_run(self):
        self.create_entry(s=self.due_later).save()

        with patch.object(self.s, 'send_task') as send_task:
            sleep = self.s.tick()
            self.assertFalse(send_task.called)

        self.assertEqual(sleep, self.s.max_interval)

    def test_due_now_never_run(self):
        e = self.create_entry(name='now', s=due_now).save()

        with patch.object(self.s, 'send_task') as send_task:
            sleep = self.s.tick()
            send_task.assert_called_with(e.task, e.args, e.kwargs, publisher=ANY, **e.options)

        self.assertEqual(sleep, 1.0)
