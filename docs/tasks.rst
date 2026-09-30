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

Listing Tasks
~~~~~~~~~~~~~
RedBeat keeps every saved entry in a sorted set at ``<redbeat_key_prefix>:schedule``,
scored by the next time each task is due. To enumerate the whole schedule, read the
keys out of that set and load each one with ``RedBeatSchedulerEntry.from_key()``::

    from redbeat import RedBeatSchedulerEntry
    from redbeat.schedulers import ensure_conf, get_redis

    conf = ensure_conf(app)
    keys = get_redis(app).zrange(conf.schedule_key, 0, -1)
    entries = [RedBeatSchedulerEntry.from_key(key, app=app) for key in keys]

A single entry can be loaded by name::

    key = RedBeatSchedulerEntry.generate_key(app, 'task-name')
    entry = RedBeatSchedulerEntry.from_key(key, app=app)

``from_key()`` raises ``KeyError`` if no such task is stored.

.. note::

    ``RedBeatScheduler.schedule`` is **not** an accessor for the stored schedule. It
    is the per-tick query Beat uses to find work: it returns only the tasks due now,
    plus at most one task due within the next ``max_interval`` so Beat can size its
    sleep. Called outside a running Beat it will usually return ``{}``, even when the
    schedule holds many tasks. Use the sorted set walk above to list everything.

Updating tasks
~~~~~~~~~~~~~~
Load an existing entry to change its frequency. Assign the new schedule and call
``save()``. Here, ``app`` is Beat's configured Celery application and ``task-name``
is an existing entry::

    from celery.schedules import schedule
    from redbeat import RedBeatSchedulerEntry
    from redbeat.schedulers import ensure_conf

    ensure_conf(app)
    key = RedBeatSchedulerEntry.generate_key(app, 'task-name')
    entry = RedBeatSchedulerEntry.from_key(key, app=app)
    entry.schedule = schedule(run_every=30, app=app)
    entry.args = ['updated', 2]
    entry.save()

For a crontab schedule, replace the schedule in the same way::

    from celery.schedules import crontab

    entry.schedule = crontab(minute='*/2', app=app)
    entry.save()

``save()`` writes the definition and updates the entry's position in the schedule.
It preserves existing runtime metadata, including ``last_run_at`` and
``total_run_count``. Beat can use the updated definition without restarting.
Call ``save()`` after changing ``schedule``, ``args``, ``kwargs``, ``options`` or
``enabled``.

Resetting the last run time
~~~~~~~~~~~~~~~~~~~~~~~~~~~
``reschedule()`` sets ``last_run_at`` to the current time and updates the entry's
position in the schedule. It leaves the saved task definition unchanged, so it
does not persist a new frequency or arguments::

    entry.reschedule()

Pass ``last_run_at`` explicitly to use a particular timestamp::

    entry.reschedule(last_run_at=app.now())

``reschedule()`` replaces the stored metadata with ``last_run_at``. A stored
``total_run_count`` is therefore reset when the entry is loaded again.

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

