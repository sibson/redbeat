from setuptools import setup

setup(
    name = "celerybeat-redis",
    description = "A Celery Beat Scheduler that uses Redis to store both schedule definitions and status information",
    version = "0.0.6",
    license = "Apache License, Version 2.0",
    author = "Kong Luoxing",
    author_email = "kong.luoxing@gmail.com",
    maintainer = "Kong Luoxing",
    maintainer_email = "kong.luoxing@gmail.com",

    keywords = "python celery beat redis",

    packages = [
        "celerybeatredis"
    ],

    install_requires=[
        'setuptools',
        'redis',
        'celery'
    ]

)
