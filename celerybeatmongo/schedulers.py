import mongoengine
import datetime

from models import *
from celery.beat import Scheduler, ScheduleEntry
from celery.utils.log import get_logger

class MongoScheduleEntry(ScheduleEntry):
    
    def __init__(self, task):
        self._task = task
        
        self.app = current_app._get_current_object()
        self.name = self._task.name
        self.task = self._task.task
        
        self.schedule = self._task.schedule
            
        self.args = self._task.args
        self.kwargs = self._task.kwargs
        self.options = {
            'queue': self._task.queue,
            'exchange': self._task.exchange,
            'routing_key': self._task.routing_key,
            'expires': self._task.expires
        }
        if self._task.total_run_count is None:
            self._task.total_run_count = 0
        self.total_run_count = self._task.total_run_count
        
        if not self._task.last_run_at:
            self._task.last_run_at = self._default_now()
        self.last_run_at = self._task.last_run_at

    def _default_now(self):
        return self.app.now()
        
    def next(self):
        self._task.last_run_at = self.app.now()
        self._task.total_run_count += 1
        return self.__class__(self._task)
        
    __next__ = next
    
    def is_due(self):
        if not self._task.enabled:
            return False, 5.0   # 5 second delay for re-enable.
        return self.schedule.is_due(self.last_run_at)
        
    def __repr__(self):
        return '<MongoScheduleEntry ({0} {1}(*{2}, **{3}) {{4}})>'.format(
            self.name, self.task, self.args,
            self.kwargs, self.schedule,
        )
        
    def reserve(self, entry):
        new_entry = Scheduler.reserve(self, entry)
        return new_entry

    def save(self):
        if self.total_run_count > self._task.total_run_count:
            self._task.total_run_count = self.total_run_count 
        if self.last_run_at and self._task.last_run_at and self.last_run_at > self._task.last_run_at:
            self._task.last_run_at = self.last_run_at
        self._task.save()
    

class MongoScheduler(Scheduler):

    
    # how often should we sync in schedule information
    # from the backend mongo database
    UPDATE_INTERVAL = datetime.timedelta(seconds=60)
    
    DATABASE = "search"
    Entry = MongoScheduleEntry
   
    def __init__(self, *args, **kwargs):
        
        self._mongo = mongoengine.connect('search')
        
        self._schedule = {}
        self._last_updated = None
        Scheduler.__init__(self, *args, **kwargs)
        self.max_interval = (kwargs.get('max_interval') \
                or self.app.conf.CELERYBEAT_MAX_LOOP_INTERVAL or 300)
      
    def setup_schedule(self):
        pass
    
    def requires_update(self):
        """check whether we should pull an updated schedule
        from the backend database"""
        if not self._last_updated:
            return True
        return self._last_updated + self.UPDATE_INTERVAL < datetime.datetime.now()
        
    def get_from_database(self):
        self.sync()
        d = {}
        for doc in PeriodicTask.objects():
            d[doc.name] = MongoScheduleEntry(doc)
        return d
     
    @property
    def schedule(self):
        if self.requires_update():
            self._schedule = self.get_from_database()
            self._last_updated = datetime.datetime.now()
        return self._schedule
    
    def sync(self):
        for entry in self._schedule.values():
            entry.save()

