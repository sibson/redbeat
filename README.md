RedBeat
=========
RedBeat is a [Celery Beat Scheduler](http://celery.readthedocs.org/en/latest/userguide/periodic-tasks.html) that stores the scheduled tasks and runtime metadata in Redis.


Why RedBeat
--------------

  1. Dynamic task creation and modification, no restart required
  1. Externally manage tasks from any language
  1. Shared data store; Beat isn't tied to a single drive
  1. Fast startup
  1. Avoid running multiple Beat servers


Getting Started
------------------

Install with pip::

    # pip install celery-redbeat

Configure RedBeat settings in your celery configuration file::

    REDBEAT_REDIS_URL = "redis://localhost:6379/1"

Then specify the scheduler when running Celery Beat::

    $ celery beat -S redbeat.RedBeatScheduler

RedBeat uses a distributed lock to prevent multiple instances running.
To disable this feature, set

    REDBEAT_LOCK_KEY = None


Configuration
----------------

    REDBEAT_REDIS_URL: URL to redis server used to store the schedule
    REDBEAT_KEY_PREFIX: A prefix for all keys created by RedBeat, default 'redbeat'
    REDBEAT_LOCK_KEY: Key used to ensure only a single beat instance runs at a time
    REDBEAT_LOCK_TIMEOUT: Unless refreshed the lock will expire after this time


Design
---------
At its core RedBeat uses a Sorted Set to store the schedule as a priority queue.
It stores task details using a hash key with the task `definition and metadata.

The schedule set contains the task keys sorted by the next scheduled run time.

For each tick of Beat

  1. get list of due keys and due next tick
  1. retrieve definitions and metadata for all keys from previous step
  1. update task metadata and reschedule with next run time of task
  1. call due tasks using async_apply
  1. calculate time to sleep until start of next tick using remaining tasks

Creating Tasks
------------------
You can use the standard CELERYBEAT_SCHEDULE to define static tasks or you can insert tasks
directly into Redis.

The easiest way to insert tasks from Python is it use RedBeatSchedulerEntry()_.

    interval = celey.schedulers.schdule(run_every=60)  # seconds
    entry = RedBeatSchedulerEntry('task-name', 'tasks.some_task', interval, args=['arg1', 2])
    entry.save()

Alternatively, you can insert directly into Redis by creating a new hash with a key of `REDBEAT_KEY_PREFIX:task-name`.
It should contain a single key `definition` which is a JSON blob with the task details.

Interval::

    {
        "name" : "interval example",
        "task" : "tasks.every_5_seconds",
        "schedule": {
            "__type__": "interval",
            "every" : 5, # seconds
            "relative": false, # optional
        },
        "args" : [  # optional
            "param1",
            "param2"
        ], 
        "kwargs" : {  # optional
            "max_targets" : 100
        },
        "enabled" : true,  # optional
    }

Crontab::

    {
        "name" : "crontab example",
        "task" : "tasks.daily",
        "schedule": {
            "__type__": "crontab",
            "minute" : "5", # optional, defaults to *
            "hour" : "*", # optional, defaults to *
            "day_of_week" : "monday", # optional, defaults to *
            "day_of_month" : "*/7", # optional, defaults to *
            "month_of_year" : "[1-12]", # optional, defaults to *
        },
        "args" : [  # optional
            "param1",
            "param2"
        ], 
        "kwargs" : {  # optional
            "max_targets" : 100
        },
        "enabled" : true,  # optional
    }

You will also need to insert the new task into the schedule with::

    zadd REDBEAT_KEY_PREFIX::schedule 0 new-task-name

The score is the next time the task should run formatted as a UNIX timestamp.

Applications may also want to manipulate the task metadata to have more control over when a task runs.
The meta key contains a JSON blob as follows

    {
        'last_run_at': {
            '__type__': 'datetime',
            'year': 2015,
            'month': 12,
            'day': 29,
            'hour': 16,
            'minute': 45,
            'microsecond': 231
        },
        'total_run_count'; 23
    }


Development
--------------
You can run the tests by 

    pip install -r requirements.dev.txt
    py.test tests

You can also quickly run a Beat instance with

    celery beat --config exmapleconf
