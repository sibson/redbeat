RedBeat
=======

.. image:: https://img.shields.io/pypi/v/celery-redbeat.svg
   :target: https://pypi.python.org/pypi/celery-redbeat
   :alt: PyPI

.. image:: https://img.shields.io/circleci/project/github/sibson/redbeat.svg
   :target: https://circleci.com/gh/sibson/redbeat/
   :alt: Circle CI

.. impage:: https://readthedocs.org/projects/redbeat/badge/?version=latest&style=flat
   :target: https://redbeat.readthedocs.io/en/latest/
   :alt: ReadTheDocs

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

More details availble on [Read the Docs](https://redbeat.readthedocs.io/en/latest/)

Development
--------------
RedBeat is available on `GitHub <https://github.com/sibson/redbeat>`_

Once you have the source you can run the tests with the following commands::

    pip install -r requirements.dev.txt
    py.test tests

You can also quickly fire up a sample Beat instance with::

    celery beat --config exampleconf
