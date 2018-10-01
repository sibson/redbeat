RedBeat
=======

.. image:: https://img.shields.io/pypi/v/celery-redbeat.svg
   :target: https://pypi.python.org/pypi/celery-redbeat
   :alt: PyPI

.. image:: https://img.shields.io/circleci/project/github/sibson/redbeat.svg
   :target: https://circleci.com/gh/sibson/redbeat/
   :alt: Circle CI

.. image:: https://img.shields.io/travis/sibson/redbeat.svg
    :target: https://travis-ci.org/sibson/redbeat
    :alt: Travis CI


`RedBeat <https://github.com/sibson/redbeat>`_ is a
`Celery Beat Scheduler <http://celery.readthedocs.org/en/latest/userguide/periodic-tasks.html>`_
that stores the scheduled tasks and runtime metadata in `Redis <http://redis.io/>`_.

Why RedBeat?
-------------

#. Dynamic live task creation and modification, without lengthy downtime
#. Externally manage tasks from any language with Redis bindings
#. Shared data store; Beat isn't tied to a single drive or machine
#. Fast startup even with a large task count
#. Prevent accidentally running multiple Beat servers

Getting Started
---------------

Install with pip:

.. code-block:: console

    pip install celery-redbeat

Configure RedBeat settings in your Celery configuration file:

.. code-block:: python

    redbeat_redis_url = "redis://localhost:6379/1"

Then specify the scheduler when running Celery Beat:

.. code-block:: console

    celery beat -S redbeat.RedBeatScheduler

RedBeat uses a distributed lock to prevent multiple instances running.
To disable this feature, set:

.. code-block:: python

    redbeat_lock_key = None

Configuration
--------------

You can add any of the following parameters to your Celery configuration
(see Celery 3.x compatible configuration value names in below).

``redbeat_redis_url``
~~~~~~~~~~~~~~~~~~~~~

URL to redis server used to store the schedule, defaults to value of
`broker_url`_.

``redbeat_key_prefix``
~~~~~~~~~~~~~~~~~~~~~~

A prefix for all keys created by RedBeat, defaults to ``'redbeat'``.

``redbeat_lock_key``
~~~~~~~~~~~~~~~~~~~~

Key used to ensure only a single beat instance runs at a time,
defaults to ``'<redbeat_key_prefix>:lock'``.

``redbeat_lock_timeout``
~~~~~~~~~~~~~~~~~~~~~~~~

Unless refreshed the lock will expire after this time, in seconds.

Defaults to five times of the default scheduler's loop interval
(``300`` seconds), so ``1500`` seconds (``25`` minutes).

See the `beat_max_loop_interval`_ Celery docs about for more information.

.. _`broker_url`: http://docs.celeryproject.org/en/4.0/userguide/configuration.html#std:setting-broker_url
.. _`beat_max_loop_interval`: http://docs.celeryproject.org/en/4.0/userguide/configuration.html#std:setting-beat_max_loop_interval

Celery 3.x config names
~~~~~~~~~~~~~~~~~~~~~~~

Here are the old names of the configuration values for use with
Celery 3.x.

===================================  ==============================================
**Celery 4.x**                       **Celery 3.x**
===================================  ==============================================
``redbeat_redis_url``                ``REDBEAT_REDIS_URL``
``redbeat_key_prefix``               ``REDBEAT_KEY_PREFIX``
``redbeat_lock_key``                 ``REDBEAT_LOCK_KEY``
``redbeat_lock_timeout``             ``REDBEAT_LOCK_TIMEOUT``
===================================  ==============================================

Design
------

At its core RedBeat uses a Sorted Set to store the schedule as a priority queue.
It stores task details using a hash key with the task definition and metadata.

The schedule set contains the task keys sorted by the next scheduled run time.

For each tick of Beat

#. get list of due keys and due next tick

#. retrieve definitions and metadata for all keys from previous step

#. update task metadata and reschedule with next run time of task

#. call due tasks using async_apply

#. calculate time to sleep until start of next tick using remaining tasks

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

On Celery 3.x the config option was called `CELERYBEAT_SCHEDULE`_.

The easiest way to insert tasks from Python is it use ``RedBeatSchedulerEntry()``::

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


Scheduling
~~~~~~~~~~~~

Assuming your `redbeat_key_prefix` config values is set to `'redbeat:'`
(default) you will also need to insert the new task into the schedule with::

    zadd redbeat::schedule 0 new-task-name

The score is the next time the task should run formatted as a UNIX timestamp.

Metadata
~~~~~~~~~~~
Applications may also want to manipulate the task metadata to have more control over when a task runs.
The meta key contains a JSON blob as follows::

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

For instance by default ```last_run_at``` corresponds to when Beat dispatched the task, but depending on queue latency it might not run immediately, but the application could update the metadata with
the actual run time, allowing intervals to be relative to last execution rather than last dispatch.

Sentinel support
~~~~~~~~~~~~~~~~

The redis connexion can use a Redis/Sentinel cluster. The
configuration syntax is inspired from `celery-redis-sentinel
<https://github.com/dealertrack/celery-redis-sentinel>`_ ::

    # celeryconfig.py
    BROKER_URL = 'redis-sentinel://redis-sentinel:26379/0'
    BROKER_TRANSPORT_OPTIONS = {
        'sentinels': [('192.168.1.1', 26379),
                      ('192.168.1.2', 26379),
                      ('192.168.1.3', 26379)],
        'password': '123',
        'service_name': 'master',
        'socket_timeout': 0.1,
    }

    CELERY_RESULT_BACKEND = 'redis-sentinel://redis-sentinel:26379/1'
    CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = BROKER_TRANSPORT_OPTIONS

Some notes about the configuration:

* note the use of ``redis-sentinel`` schema within the URL for broker and results
  backend.

* hostname and port are ignored within the actual URL. Sentinel uses transport options
  ``sentinels`` setting to create a ``Sentinel()`` instead of configuration URL.

* ``password`` is going to be used for Celery queue backend as well.

If other backend is configured for Celery queue use
``REDBEAT_REDIS_URL`` instead of ``BROKER_URL`` and
``REDBEAT_REDIS_OPTIONS`` instead of ``BROKER_TRANSPORT_OPTIONS``. to
avoid conflicting options. Here follows the example:::

    # celeryconfig.py
    REDBEAT_REDIS_URL = 'redis-sentinel://redis-sentinel:26379/0'
    REDBEAT_REDIS_OPTIONS = {
        'sentinels': [('192.168.1.1', 26379),
                      ('192.168.1.2', 26379),
                      ('192.168.1.3', 26379)],
        'password': '123',
        'service_name': 'master',
        'socket_timeout': 0.1,
        'retry_period': 60,
    }

If ``retry_period`` is given, retry connection for ``retry_period``
seconds. If not set, retrying mechanism is not triggered. If set
to ``-1`` retry infinitely.



Development
--------------
RedBeat is available on `GitHub <https://github.com/sibson/redbeat>`_

Once you have the source you can run the tests with the following commands::

    pip install -r requirements.dev.txt
    py.test tests

You can also quickly fire up a sample Beat instance with::

    celery beat --config exampleconf
