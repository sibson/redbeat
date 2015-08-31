from setuptools import setup

setup(
    name="celery-redbeat",
    description="A Celery Beat Scheduler using Redis for persistent storage",
    version="0.8.0",
    url="https://github.com/sibson/redbeat",
    license="Apache License, Version 2.0",
    author="Marc Sibson",
    author_email="sibson+redbeat@gmail.com",
    keywords="python celery beat redis".split(),
    packages=[
        "redbeat"
    ],
    install_requires=[
        'redis',
        'celery'
    ]
)
