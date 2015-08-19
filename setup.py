from setuptools import setup

setup(
    name="celery-redbeat",
    description="A Celery Beat Scheduler using Redis for persistent storage",
    version="0.5.0",
    license="Apache License, Version 2.0",
    author="Marc Sibson",
    author_email="sibson@gmail.com",
    keywords="python celery beat redis",
    packages=[
        "redbeat"
    ],
    install_requires=[
        'redis',
        'celery'
    ]
)
