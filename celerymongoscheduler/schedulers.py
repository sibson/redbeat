import datetime

from celery.beat import Scheduler, ScheduleEntry
from celery.utils.log import get_logger

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

    def _default_now(self):
        return self.app.now()
        
    def next(self):
        self._task.last_run_at = self.app.now()
        self._task.total_run_count += 1
        return self.__class__(self._task)
        
    __next__ = next
    
    def is_due(self):
        if not self.model.enabled:
            return False, 5.0   # 5 second delay for re-enable.
        return self.schedule.is_due(self.last_run_at)
        
    def __repr__(self):
        return '<MongoScheduleEntry ({0} {1}(*{2}, **{3}) {{4}})>'.format(
            safe_str(self.name), self.task, safe_repr(self.args),
            safe_repr(self.kwargs), self.schedule,
        )
        
    def reserve(self, entry):
        new_entry = Scheduler.reserve(self, entry)
        return new_entry

    def save(self):
        if self.total_run_count > self._task.total_run_count:
            self._task.total_run_count = self.total_run_count 
        if self.last_run_at > self._task.last_run_at:
            self._task.last_run_at = self.last_run_at
        self._task.save()
    

class MongoScheduler(Scheduler):
    
    # how often should we sync in schedule information
    # from the backend mongo database
    UPDATE_INTERVAL = datetime.timedelta(minutes=5)
    
    DATABASE = "search"
    
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
        self.sync()
        d = {}
        for doc in PeriodicTask.objects():
            d[doc.name] = MongoScheduleEntry(doc)
        return d
        
    @property
    def schedule(self):
        if self.requires_update():
            self._schedule = get_from_database()
        return self._schedule
    
    def sync(self):
        for entry in self._schedule.values:
            entry.save()
