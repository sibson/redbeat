# Copyright 2013 Regents of the University of Michigan 

# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0

import datetime
from mongoengine import *
from celery import current_app
import celery.schedules

def get_periodic_task_collection():
    if hasattr(current_app.conf, "CELERY_MONGODB_SCHEDULER_COLLECTION") \
            and current_app.conf.CELERY_MONGODB_SCHEDULER_COLLECTION:
        return current_app.conf.CELERY_MONGODB_SCHEDULER_COLLECTION
    return "schedules"

class PeriodicTask(Document):
    """mongo database model that represents a periodic task"""

    meta = {'collection':get_periodic_task_collection()} 
    
    class Interval(EmbeddedDocument):
    
        every = IntField(min_value=0)
        period = StringField()
    
        @property
        def schedule(self):
            return celery.schedules.schedule(datetime.timedelta(**{self.period: self.every}))
    
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
    
        @property
        def schedule(self):
            return celery.schedules.crontab(minute=self.minute,
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
    interval = EmbeddedDocumentField(Interval)
    crontab = EmbeddedDocumentField(Crontab)
    
    args = ListField(StringField())
    kwargs = DictField()
    
    queue = StringField()
    exchange = StringField()
    routing_key = StringField()
    
    expires = DateTimeField()
    enabled = BooleanField()
    
    last_run_at = DateTimeField()
    
    total_run_count = IntField(min_value=0)
    
    date_changed = DateTimeField()
    description = StringField()

    #objects = managers.PeriodicTaskManager()
    no_changes = False
    
    def clean(self):
        """validation by mongoengine to ensure that you only have
        an interval or crontab schedule, but not both simultaneously"""
        if self.interval and self.crontab:
            msg = 'Cannot define both interval and crontab schedule.'
            raise ValidationError(msg)
        if not (self.interval or self.crontab):
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

