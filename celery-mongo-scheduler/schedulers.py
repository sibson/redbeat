from __future__ import absolute_import

import logging

from multiprocessing.util import Finalize

from anyjson import loads, dumps
from celery import current_app
from celery import schedules
from celery.beat import Scheduler, ScheduleEntry
from celery.utils.encoding import safe_str, safe_repr
from celery.utils.log import get_logger
from celery.utils.timeutils import is_naive

logger = get_logger(__name__)
debug, info, error = logger.debug, logger.info, logger.error


class PeriodicTasks(models.Model):
    ident = models.SmallIntegerField(default=1, primary_key=True, unique=True)
    last_update = models.DateTimeField(null=False)

    objects = managers.ExtendedManager()

    @classmethod
    def changed(cls, instance, **kwargs):
        if not instance.no_changes:
            cls.objects.update_or_create(ident=1,
                                         defaults={'last_update': now()})

    @classmethod
    def last_change(cls):
        try:
            return cls.objects.get(ident=1).last_update
        except cls.DoesNotExist:
            pass


class ModelEntry(ScheduleEntry):
    model_schedules = (
        (schedules.crontab, =, 'crontab'),
        (schedules.schedule, IntervalSchedule, 'interval')
    )
    
    save_fields = ['last_run_at', 'total_run_count', 'no_changes']

        model.no_changes = True
        model.enabled = False


    def save(self):
        # Object may not be synchronized, so only
        # change the fields we care about.
        obj = self.model._default_manager.get(pk=self.model.pk)
        for field in self.save_fields:
            setattr(obj, field, getattr(self.model, field))
        obj.last_run_at = make_aware(obj.last_run_at)
        obj.save()
        


class DatabaseScheduler(Scheduler):
    Entry = ModelEntry
    Model = PeriodicTask
    Changes = PeriodicTasks
    _schedule = None
    _last_timestamp = None
    _initial_read = False

    def __init__(self, *args, **kwargs):
        self._dirty = set()
        self._finalize = Finalize(self, self.sync, exitpriority=5)
        Scheduler.__init__(self, *args, **kwargs)
        self.max_interval = (kwargs.get('max_interval') or self.app.conf.CELERYBEAT_MAX_LOOP_INTERVAL or DEFAULT_MAX_INTERVAL)

    def sync(self):
        info('Writing entries...')
        _tried = set()
        try:
            with commit_on_success():
                while self._dirty:
                    try:
                        name = self._dirty.pop()
                        _tried.add(name)
                        self.schedule[name].save()
                    except (KeyError, ObjectDoesNotExist):
                        pass
        except DATABASE_ERRORS as exc:
            # retry later
            self._dirty |= _tried
            error('Database error while sync: %r', exc, exc_info=1)
            

    @property
    def schedule(self):
        update = False
        if not self._initial_read:
            debug('DatabaseScheduler: intial read')
            update = True
            self._initial_read = True
        elif self.schedule_changed():
            info('DatabaseScheduler: Schedule changed.')
            update = True

        if update:
            self.sync()
            self._schedule = self.all_as_schedule()
            if logger.isEnabledFor(logging.DEBUG):
                debug('Current schedule:\n%s', '\n'.join(
                    repr(entry) for entry in self._schedule.itervalues()),
                )
        return self._schedule