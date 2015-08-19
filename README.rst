Red Beat
################

Github page: https://github.com/sibson/redbeat

It's modified from celerybeat-mongo (https://github.com/zakird/celerybeat-mongo)

This is a [Celery Beat Scheduler](http://celery.readthedocs.org/en/latest/userguide/periodic-tasks.html)
that stores both the schedules themselves and their status information in a Redis database. 

It can be installed via pip::

    # pip install celery-redbeat

Then specify the scheduler when running Celery Beat::

    $ celery beat -S redbeat.RedisBeatScheduler

To configure you will need to set two settings in your celery configuration file::

    REDBEAT_REDIS_URL = "redis://localhost:6379/1"
    REDBEAT_KEY_PREFIX = 'tasks:meta:'

redbeat will create a redis hash with a key of `REDBEAT_KEY_PREFIX:task-name`.
The hash contains two keys `periodic` which is a JSON blob with the task details and `meta`
which contains metadata for the scheduler.

You can either create new tasks using Python to create and save a new PeriodicTask()_ or
you can create them directly in Redis.

The format of task definitions is as follow

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
    }

The following fields are required: name, task, enabled, crontab|interval when defining new tasks.
