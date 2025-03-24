Creating Tasks
---------------

You can use Celery's usual way to define static tasks or you can insert tasks
directly into Redis. The config options is called `beat_schedule`_, e.g.:

.. code-block:: python

    app.conf.beat_schedule = {
        'add-every-30-seconds': {
            'task': 'tasks.add',
            'schedule': 30.0,
            'args': (16, 16)
        },
    }

The easiest way to insert tasks from Python is it use ``RedBeatSchedulerEntry()``::

    from redbeat import RedBeatSchedulerEntry
    interval = celery.schedules.schedule(run_every=60)  # seconds
    entry = RedBeatSchedulerEntry('task-name', 'tasks.some_task', interval, args=['arg1', 2])
    entry.save()

Alternatively, you can insert directly into Redis by creating a new hash with
a key of ``<redbeat_key_prefix>:task-name``. It should contain a single key
``definition`` which is a JSON blob with the task details.

.. _`CELERYBEAT_SCHEDULE`: http://docs.celeryproject.org/en/3.1/userguide/periodic-tasks.html#beat-entries
.. _`beat_schedule`: http://docs.celeryproject.org/en/4.0/userguide/periodic-tasks.html#beat-entries

Interval
~~~~~~~~
An interval task is defined with the JSON like::

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

Crontab
~~~~~~~
An crontab task is defined with the JSON like::

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

