import datetime

from celery.utils.timeutils import is_naive
from celery.beat import Scheduler, ScheduleEntry
from celery.utils.log import get_logger

class PeriodicTask(Document):
    """mongo database model that represents a periodic task"""
    
    class Interval(EmbeddedDocument):
    
        every = IntegerField(min=0)
        period = StringField()
    
        @property
        def schedule(self):
            return schedules.schedule(timedelta(**{self.period: self.every}))
    
        @property
        def period_singular(self):
            return self.period[:-1]
        
        def __unicode__(self):
            if self.every == 1:
                return _('every {0.period_singular}').format(self)
            return _('every {0.every} {0.period}').format(self)


    class Crontab(EmbeddedDocument):
    
        minute = StringField()
        hour = StringField()
        day_of_week = StringField()
        day_of_month = StringField()
        day_of_year = StringField()
    
        @property()
        def schedule(self):
            return schedules.crontab(minute=self.minute,
                                     hour=self.hour,
                                     day_of_week=self.day_of_week,
                                     day_of_month=self.day_of_month,
                                     month_of_year=self.month_of_year)
        
        def __unicode__(self):
            rfield = lambda f: f and str(f).replace(' ', '') or '*'
            return '{0} {1} {2} {3} {4} (m/h/d/dM/MY)'.format(
                rfield(self.minute), rfield(self.hour), rfield(self.day_of_week),
                rfield(self.day_of_month), rfield(self.month_of_year),
            )

    name = StringField()
    task = StringField()

    type_ = StringField()
    interval = EmbeddedDocument(Interval)
    crontab = EmbeddedDocument(Crontab)
    
    args = ListField(StringField())
    kwargs = DictField()
    
    queue = StringField()
    exchange = StringField()
    routing_key = StringField()
    
    expires = DateTimeField()
    enabled = BooleanField()
    
    last_run_at = DateTimeField()
    
    total_run_count = IntField(min=0)
    
    date_changed = DateTimeField()
    description = StringField()

    objects = managers.PeriodicTaskManager()
    no_changes = False
    
    def clean(self):
        """validation by mongoengine to ensure that you only have
        an interval or crontab schedule, but not both simultaneously"""
        if self.interval and self.crontab:
            msg = 'Cannot define both interval and crontab schedule.'
            raise ValidationError(msg)
        if not (self.interval or self.crontab)
            msg = 'Must defined either interval or crontab schedule.'
            raise ValidationError(msg)

    @property
    def schedule(self):
        if self.interval:
            return self.interval.schedule
        elif self.crontab:
            return self.crontab.schedule
        else:
            raise Exception("must define internal or crontab schedule")
            
    def __unicode__(self):
        fmt = '{0.name}: {{no schedule}}'
        if self.interval:
            fmt = '{0.name}: {0.interval}'
        elif self.crontab:
            fmt = '{0.name}: {0.crontab}'
        else:
            raise Exception("must define internal or crontab schedule") 
        return fmt.format(self)


class MongoScheduleEntry(ScheduleEntry):
    
    def __init__(self, task):
        self._task = task
        
        self.app = current_app._get_current_object()
        self.name = self._task.name
        self.task = self._task.task
        
        self.schedule = self._task.schedule
            
        self.args = self.args
        self.kwargs = self._task.kwargs
        self.options = {
            'queue': model.queue,
            'exchange': model.exchange,
            'routing_key': model.routing_key,
            'expires': model.expires
        }
        self.total_run_count = self._task.total_run_count
        
        if not self._task.last_run_at:
            self._task.last_run_at = self._default_now()
            
        self.is_dirty = False
        

    def _default_now(self):
        return self.app.now()
        
    def next(self):
        self._task.last_run_at = self.app.now()
        self._task.total_run_count += 1
        self.is_dirty = True
        return self.__class__(self._task)
        
    __next__ = next
    
    def is_due(self):
        if not self.model.enabled:
            return False, 5.0   # 5 second delay for re-enable.
        return self.schedule.is_due(self.last_run_at)
        
    def __repr__(self):
        return '<ModelEntry: {0} {1}(*{2}, **{3}) {{4}}>'.format(
            safe_str(self.name), self.task, safe_repr(self.args),
            safe_repr(self.kwargs), self.schedule,
        )
        
    def reserve(self, entry):
        new_entry = Scheduler.reserve(self, entry)
        #self._dirty.add(new_entry.name)
        return new_entry
        
        
    def sync(self):
        while self.dirty():
            self._scheduler[self.dirty.pop()].save()
        
    

class MongoScheduler(Scheduler):
    
    # how often should we sync in schedule information
    # from the backend mongo database
    UPDATE_INTERVAL = datetime.timedelta(minutes=5)
    
    DATABASE = "search"
    COLLECTION = "periodic_tasks"
    
    def __init__(self, *args, **kwargs):
        
        self._mongo = mongoengine.connect('search')
        
        Scheduler.__init__(self, *args, **kwargs)
        self.max_interval = (kwargs.get('max_interval') \
                or self.app.conf.CELERYBEAT_MAX_LOOP_INTERVAL \
                or DEFAULT_MAX_INTERVAL)
                
        self.__last_updated = None
        self.__schedule = []
    
    def requires_update(self):
        """check whether we should pull an updated schedule
        from the backend database"""
        if not self.__last_updated:
            return True
        return self.__last_updated + self.UPDATE_INTERVAL < datetime.datetime.now()
        
    def get_from_database(self):
        d = {}
        for doc in PeriodicTask.objects()
            d[doc.name] = MongoScheduleEntry(doc)
        return d
        
    @property
    def schedule(self):
        if self.requires_update():
            self._schedule = get_from_database()
        return self._schedule
        
    def sync(self):
        pass