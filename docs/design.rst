
Design
------

At its core RedBeat uses a Sorted Set to store the schedule as a priority queue.
It stores task details using a hash key with the task definition and metadata.

The schedule set contains the task keys sorted by the next scheduled run time.

For each tick of Beat

#. check if it still owns the lock, if not, exit with ``LockNotOwnedError``

#. get list of due keys and due next tick

#. retrieve definitions and metadata for all keys from previous step

#. update task metadata and reschedule with next run time of task

#. call due tasks using async_apply

#. calculate time to sleep until start of next tick using remaining tasks

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

High Availability
~~~~~~~~~~~~~~~~~

Redbeat use a lock in redis to prevent multiple node running.
You can safely start multiple nodes as backup, when the running node fails or
experience network problems, after ``redbeat_lock_timeout`` seconds,
another node will acquire the lock and start running.

When the previous node back online, it will notice that itself no longer holds
the lock and exit with an Exception(Would be better if you use systemd or supervisord
to restart it as a backup node).
