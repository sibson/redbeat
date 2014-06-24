from setuptools import setup

setup(
    name = "celerybeat-mongo",
    description = "A Celery Beat Scheduler that uses MongoDB to store both schedule definitions and status information",
    version = "0.0.3",
    license = "Apache License, Version 2.0",
    author = "Zakir Durumeric",
    author_email = "zakird@gmail.com",
    maintainer = "Zakir Durumeric",
    maintainer_email = "zakird@gmail.com",

    keywords = "python celery beat mongo",

    packages = [
        "celerybeatmongo"
    ],

    install_requires=[
        'setuptools',
        'pymongo',
        'mongoengine',
        'celery',
    ]

)
