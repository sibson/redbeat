celerybeat-redis
################

Github page: https://github.com/jayklx/celerybeatredis

It's modified from celerybeat-mongo (https://github.com/zakird/celerybeat-mongo)

This is a Celery Beat Scheduler (http://celery.readthedocs.org/en/latest/userguide/periodic-tasks.html)
that stores both the schedules themselves and their status
information in a backend Redis database. It can be installed by
installing the celerybeat-redis Python egg::

    # pip install celerybeat-redis

And specifying the scheduler when running Celery Beat, e.g.::

    $ celery beat -S celerybeatredis.schedulers.RedisScheduler

Settings for the scheduler are defined in your celery configuration file
similar to how other aspects of Celery are configured::

    CELERY_REDIS_SCHEDULER_URL = "redis://localhost:6379/1"
    CELERY_REDIS_SCHEDULER_KEY_PREFIX = 'tasks:meta:'

You mush make these two value configured.
CELERY_REDIS_SCHEDULER_KEY_PREFIX is used to generate keys in redis.
The key was like::

    tasks:meta:task-name-here:sha1-hash-value
    tasks:meta:test-fib-every-3s:efff8ee06703c4cffad73834154a609dab0e1161

Schedules can be manipulated in the Redis database through
direct database manipulation. There exist two types of schedules,
interval and crontab.
crontab are not much tested yet.

Interval::

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
	    "last_run_at" : {
	        "__type__", "datetime",
	        "year": 2014,
	        "month": 8,
	        "day": 30,
	        "hour": 8,
	        "minute": 10,
	        "second": 6,
	        "microsecond": 667
	    }
    }

The example from Celery User Guide::Periodic Tasks. ::

    {
    	CELERYBEAT_SCHEDULE = {
    	    'interval-test-schedule': {
    	        'task': 'tasks.add',
    	        'schedule': timedelta(seconds=30),
    	        'args': (param1, param2)
    	    }
    	}
    }

Becomes the following::

    {
        "name" : "interval test schedule",
        "task" : "task.add",
        "enabled" : true,
        "interval" : {
            "every" : 30,
            "period" : "seconds",
        },
        "args" : [
            "param1",
            "param2"
        ],
        "kwargs" : {
            "max_targets" : 100
        }
        "total_run_count": 5,
	    "last_run_at" : {
	        "__type__", "datetime",
	        "year": 2014,
	        "month": 8,
	        "day": 30,
	        "hour": 8,
	        "minute": 10,
	        "second": 6,
	        "microsecond": 667
	    }
    }

The following fields are required: name, task, crontab || interval,
enabled when defining new tasks.
total_run_count and last_run_at are maintained by the
scheduler and should not be externally manipulated.


WARNING: crontab feature was not well tested. Bugs will be fixed later.

The example from Celery User Guide::Periodic Tasks.
(see: http://docs.celeryproject.org/en/latest/userguide/periodic-tasks.html#crontab-schedules)::

	{

		CELERYBEAT_SCHEDULE = {
		    # Executes every Monday morning at 7:30 A.M
		    'add-every-monday-morning': {
		        'task': 'tasks.add',
		        'schedule': crontab(hour=7, minute=30, day_of_week=1),
		        'args': (16, 16),
		    },
		}
	}

Becomes::

	{
	    "_id" : ObjectId("53a91dfd455d1c1a4345fb59"),
	    "name" : "add-every-monday-morning",
	    "task" : "tasks.add",
	    "enabled" : true,
	    "crontab" : {
	        "minute" : "30",
	        "hour" : "7",
	        "day_of_week" : "1",
	        "day_of_month" : "*",
	        "month_of_year" : "*"
	    },
	    "args" : [
	        "16",
	        "16"
	    ],
	    "kwargs" : {},
	    "total_run_count" : 1,
	    "last_run_at" : {
	        "__type__", "datetime",
	        "year": 2014,
	        "month": 8,
	        "day": 30,
	        "hour": 8,
	        "minute": 10,
	        "second": 6,
	        "microsecond": 667
	    }
	}
