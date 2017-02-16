from setuptools import setup

long_description = open('README.rst').read()

setup(
    name="celery-redbeat",
    description="A Celery Beat Scheduler using Redis for persistent storage",
    long_description=long_description,
    version="0.10.0rc1",
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
        'celery',
    ],
    tests_require=[
        'pytest',
    ],
)
