celerybeat-mongo
################

This is a Celery Beat Scheduler (http://celery.readthedocs.org/en/latest/userguide/periodic-tasks.html)
that stores both the schedules themselves and their status
information in a backend Mongo database. It can be installed by 
installing the celerybeat-mongo Python egg::

    # pip install celerybeat-mongo 

And specifying the scheduler when running Celery Beat, e.g.::

    $ celery beat -S celerybeatmongo.schedulers.MongoScheduler

Settings for the scheduler are defined in your celery configuration file
similar to how other aspects of Celery are configured::

    CELERY_MONGODB_SCHEDULER_DB = "celery"
    CELERY_MONGODB_SCHEDULER_COLLECTION = "schedules"
    CELERY_MONGODB_SCHEDULER_URL = "mongodb://userid:password@hostname:port"

If not settings are specified, the library will attempt to use the schedules collection in the local celery database.

Schedules can be manipulated in the Mongo database using the
mongoengine models in celerybeatmongo.models or through
direct database manipulation. There exist two types of schedules,
interval and crontab.

Interval::

    {
        "_id" : ObjectId("533c5b29b45a2092bffceb13"),
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
        "last_run_at" : ISODate("2014-04-03T19:19:22.666+17:00")
    }

Crontab::

    {
        "_id" : ObjectId("53a91dfd455d1c1a4345fb59"),
        "name" : "crontab test schedule",
        "task" : "task-name-goes-here",
        "enabled" : true,
        "crontab" : {
            "minute" : "30",
            "hour" : "2",
            "day_of_week" : "*",
            "day_of_month" : "*",
            "day_of_year" : "*"
        },
        "args" : [
            "param1",
            "param2"
        ],
        "kwargs" : {
            "max_targets" : 100
        },
        "total_run_count" : 5,
        "last_run_at" : ISODate("2014-04-03T19:19:22.666+17:00")
    }

The following fields are required: name, task, crontab || interval,
enabled when defining new tasks.
total_run_count and last_run_at are maintained by the
scheduler and should not be externally manipulated.
