from setuptools import setup

long_description = open('README.rst').read()

setup(
    name="celery-redbeat",
    description="A Celery Beat Scheduler using Redis for persistent storage",
    long_description=long_description,
    version="2.69.0",
    url="https://github.com/sibson/redbeat",
    license="Apache License, Version 2.0",
    author="Marc Sibson",
    author_email="sibson+redbeat@gmail.com",
    keywords="python celery beat redis".split(),
    packages=["redbeat"],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: Apache Software License',
        'Topic :: System :: Distributed Computing',
        'Topic :: Software Development :: Object Brokering',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Operating System :: OS Independent',
    ],
    install_requires=[
        'redis>=3.2',
        'celery @ git+https://github.com/HiveHQ/celery.git#egg=celery',
        'python-dateutil>=2.4.2',
        'tenacity==7.0.0',
    ],
    tests_require=['pytest'],
)
