celerybeat-redis
################

This is a Celery Beat Scheduler (http://celery.readthedocs.org/en/latest/userguide/periodic-tasks.html)
It's modified from celerybeat-mongo(https://github.com/zakird/celerybeat-mongo)

that stores both the schedules themselves and their status
information in a backend redis database. It can be installed by 
installing the celerybeat-redis Python egg::

    # pip install celerybeat-redis 

And specifying the scheduler when running Celery Beat, e.g.::

    $ celery beat -S celerybeatredis.schedulers.RedisScheduler

Settings for the scheduler are defined in your celery configuration file
similar to how other aspects of Celery are configured::

    CELERY_REDIS_SCHEDULER_KEY_PREFIX = 'tasks:meta:'
    CELERY_REDIS_SCHEDULER_URL = 'redis://localhost:6379/1'

If not settings are specified, the library will attempt to use the schedules collection in the local celery database.

Schedules can be manipulated in the redis by
direct database manipulation. There exist two types of schedules,
interval and crontab.

Interval::
key: task:meta:name:hash
    {
        "name" : "interval test schedule",
        "task" : "task-name-goes-here",
        "enabled" : true,
        "interval" : {
            "every" : 5,
            "period" : "minutes"
        },
        "args" : [
            "param1",
            "param2"
        ],
        "kwargs" : {
            "max_targets" : 100
        },
        "total_run_count" : 5,
        "last_run_at" : ISODate("2014-04-03T19:19:22.666+17:00")
    }

The example from Celery User Guide::Periodic Tasks. ::

    {
    	CELERYBEAT_SCHEDULE = {
    	    'add-every-30-seconds': {
    	        'task': 'tasks.add',
    	        'schedule': timedelta(seconds=30),
    	        'args': (16, 16)
    	    },
    	}
    }

Becomes the following::

    {
        "name" : "crontab test schedule",
        "task" : "task-name-goes-here",
        "enabled" : true,
        "crontab" : {
            "minute" : "30",
            "hour" : "2",
            "day_of_week" : "*",
            "day_of_month" : "*",
            "month_of_year" : "*"
        },
        "args" : [
            "param1",
            "param2"
        ],
        "kwargs" : {
            "max_targets" : 100
        },
        "total_run_count" : 5,
        "last_run_at" : {
        "__type__": "datetime",
        "year": 2014,
        "month": 8,
        "day": 31,
        "hour": 9,
        "minute": 5,
        "second": 10,
        "microsecond" "667"
        }
    }


The following fields are required: name, task, crontab || interval,
enabled when defining new tasks.
total_run_count and last_run_at are maintained by the
scheduler and should not be externally manipulated.
