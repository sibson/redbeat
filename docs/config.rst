Configuration
--------------

You can add any of the following parameters to your Celery configuration
(see Celery 3.x compatible configuration value names in below).

``redbeat_redis_url``
~~~~~~~~~~~~~~~~~~~~~

URL to redis server used to store the schedule, defaults to value of
`broker_url`_.

``redbeat_redis_use_ssl``
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Additional SSL options used when using the ``rediss`` scheme in
``redbeat_redis_url``, defaults to the values of `broker_use_ssl`_.

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
.. _`broker_use_ssl`: http://docs.celeryproject.org/en/4.0/userguide/configuration.html#std:setting-broker_use_ssl
.. _`beat_max_loop_interval`: http://docs.celeryproject.org/en/4.0/userguide/configuration.html#std:setting-beat_max_loop_interval

Celery 3.x config names
~~~~~~~~~~~~~~~~~~~~~~~

Here are the old names of the configuration values for use with
Celery 3.x.

===================================  ==============================================
**Celery 4.x**                       **Celery 3.x**
===================================  ==============================================
``redbeat_redis_url``                ``REDBEAT_REDIS_URL``
``redbeat_redis_use_ssl``            ``REDBEAT_REDIS_USE_SSL``
``redbeat_key_prefix``               ``REDBEAT_KEY_PREFIX``
``redbeat_lock_key``                 ``REDBEAT_LOCK_KEY``
``redbeat_lock_timeout``             ``REDBEAT_LOCK_TIMEOUT``
===================================  ==============================================

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
        'db': 0,
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

* ``db`` is optional and defaults to ``0``.

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


