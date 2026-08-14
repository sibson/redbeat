Configuration
--------------

You can add any of the following parameters to your Celery configuration:

``redbeat_redis_url``
~~~~~~~~~~~~~~~~~~~~~

URL to redis server used to store the schedule, defaults to value of
`broker_url`_. Both Redis and Valkey servers are supported.

.. deprecated:: 2.4.2
   The fallback to `broker_url`_ is deprecated and will be removed in
   RedBeat 2.5.0; set ``redbeat_redis_url`` explicitly.

``redbeat_redis_options``
~~~~~~~~~~~~~~~~~~~~~~~~~

Options for the redis connection used to store the schedule. RedBeat
consumes its own keys from this dict (``retry_period``, ``cluster``,
``sentinels``, ``service_name``, ``sentinel_kwargs``, ``startup_nodes``)
and passes everything else through to the redis client, so any option
accepted by redis-py (``password``, ``socket_timeout``,
``credential_provider``, ...) can be given here. Unknown options are
rejected by redis-py itself.

If not set, RedBeat falls back to `broker_transport_options`_. Inherited
broker options are not forwarded to the redis client on ``redis://`` and
``rediss://`` URLs (the behavior before 2.4.0); RedBeat only reads its own
keys from them, and the sentinel and cluster backends keep reading the
options documented below. Set ``redbeat_redis_options`` explicitly to pass
connection options through to the client.

If ``retry_period`` is given, retry the connection for ``retry_period``
seconds. If not set, the retrying mechanism is not triggered. If set
to ``-1`` retry infinitely.

.. deprecated:: 2.4.2
   The fallback to `broker_transport_options`_ is deprecated and will be
   removed in RedBeat 2.5.0; set ``redbeat_redis_options`` explicitly.

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

``redbeat_key_expiry_check``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

What RedBeat does at startup when it finds Redis configured to let its keys
expire or be evicted, see requirements_ below. One of:

``'ignore'``
    Skip the checks entirely, and the two commands they cost.
``'warn'``
    Log any finding at ``WARNING``.
``'error'``
    Log any finding at ``ERROR``. The default.
``'raise'``
    Log any finding at ``ERROR``, then refuse to start.

.. versionadded:: 2.4.3

``redbeat_lock_timeout``
~~~~~~~~~~~~~~~~~~~~~~~~

Unless refreshed the lock will expire after this time, in seconds.

Defaults to five times of the default scheduler's loop interval
(``300`` seconds), so ``1500`` seconds (``25`` minutes).

See the `beat_max_loop_interval`_ Celery docs about for more information.

.. _`broker_url`: http://docs.celeryproject.org/en/4.0/userguide/configuration.html#std:setting-broker_url
.. _`broker_use_ssl`: http://docs.celeryproject.org/en/4.0/userguide/configuration.html#std:setting-broker_use_ssl
.. _`broker_transport_options`: http://docs.celeryproject.org/en/4.0/userguide/configuration.html#std:setting-broker_transport_options
.. _`beat_max_loop_interval`: http://docs.celeryproject.org/en/4.0/userguide/configuration.html#std:setting-beat_max_loop_interval

Sentinel support
~~~~~~~~~~~~~~~~

The redis connection can use a Redis/Sentinel cluster. The
configuration syntax is inspired from `celery-redis-sentinel
<https://github.com/dealertrack/celery-redis-sentinel>`_ ::

    # celeryconfig.py
    REDBEAT_REDIS_URL = 'redis-sentinel://redis-sentinel:26379/0'
    REDBEAT_REDIS_OPTIONS = {
        'sentinels': [('192.168.1.1', 26379),
                      ('192.168.1.2', 26379),
                      ('192.168.1.3', 26379)],
        'password': '123',
        'db': 0,
        'service_name': 'master',
        'socket_timeout': 0.1,
        'sentinel_kwargs': {'password': 'sentinel_password'},
        'retry_period': 60,
    }

Some notes about the configuration:

* note the use of ``redis-sentinel`` schema within the URL.

* hostname and port are ignored within the actual URL. Sentinel uses
  the ``sentinels`` setting to create a ``Sentinel()`` instead of
  the configuration URL.

* ``db`` is optional and defaults to ``0``.

* ``sentinel_kwargs`` is optional and is passed to ``redis.Sentinel()``.
  For example, if sentinel has set a password, ``sentinel_kwargs`` can be
  set to ``{'password': 'sentinel_password'}``

Until 2.5.0 RedBeat will still fall back to ``BROKER_URL`` and
``BROKER_TRANSPORT_OPTIONS`` when the ``REDBEAT_*`` settings are not
given, but that fallback is deprecated: ``BROKER_TRANSPORT_OPTIONS``
belongs to the broker and mixes in settings (``visibility_timeout``, ...)
that have no meaning for RedBeat's redis connection.

Redis Cluster support
~~~~~~~~~~~~~~~~~~~~~

The redis connection can use a Redis cluster::

    # celeryconfig.py
    REDBEAT_REDIS_URL = 'redis-cluster://redis-cluster:30001/0'
    REDBEAT_REDIS_OPTIONS = {
        'startup_nodes': [{"host": "192.168.1.1", "port": "30001"},
                          {"host": "192.168.1.2", "port": "30002"},
                          {"host": "192.168.1.3", "port": "30003"},
                          {"host": "192.168.1.4", "port": "30004"}],
        'password': '123',
    }

Some notes about the configuration:

* note the use of ``redis-cluster`` schema within the URL.

* hostname and port are ignored within the actual URL. Redis Cluster
  uses the ``startup_nodes`` option, and the remaining options are sent
  as keyword arguments to ``RedisCluster()``.

.. _requirements:

Redis requirements
------------------

RedBeat's keys are the schedule, not a cache of it. Nothing recreates them:
an entry whose hash disappears stops running, and RedBeat notices only when
the entry next comes due, at which point it logs

.. code-block:: text

    beat: Failed to load redbeat:some-task, removing; its hash is gone, which
    usually means Redis evicted or expired it

Entries defined in ``beat_schedule`` come back at the next beat restart;
entries created through the API are gone for good. So RedBeat's keys must
never expire, and the Redis holding them must never evict them.

Two ways deployments break that:

* an eviction policy. With ``maxmemory`` set and a ``maxmemory-policy`` in
  the ``allkeys-*`` family, Redis may drop any key, including the schedule,
  once memory runs short. The ``volatile-*`` policies only drop keys carrying
  an expiry.
* an expiry on the keys themselves, usually housekeeping on a shared Redis,
  or a ``redbeat:*`` sweep modelled on the lock key.

Use the ``noeviction`` policy, or give RedBeat a Redis instance or database
of its own. ``redbeat::lock`` is the one deliberate exception: it is supposed
to expire, that is what releases the lock when a beat process dies.

At startup RedBeat checks what it can afford to check: whether
``redbeat::schedule`` or ``redbeat::statics`` carry an expiry, and whether
the server reports an evicting ``maxmemory-policy``. Findings are logged and
repeated in the beat banner, under the control of ``redbeat_key_expiry_check``
above. It does not walk the individual entry hashes, which would cost a round
trip per entry on every beat startup. To check those by hand::

    redis-cli --scan --pattern 'redbeat:*' | while read key; do
        ttl=$(redis-cli ttl "$key")
        test "$ttl" -ge 0 && echo "$key expires in ${ttl}s"
    done

The startup check needs no more than ``CONFIG GET``, and quietly skips the
policy half when the server refuses it, as several managed Redis offerings
do. A server RedBeat cannot ask is never reported as unsafe, so on those
deployments check ``maxmemory-policy`` yourself through the provider console.

Programs that create entries through the API without running beat never reach
the startup check, since it is beat that runs it.
