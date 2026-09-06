from importlib.metadata import PackageNotFoundError, version

from .checks import RedBeatKeyExpiryError  # noqa
from .schedulers import RedBeatScheduler, RedBeatSchedulerEntry  # noqa

try:
    __version__ = version('celery-redbeat')
except PackageNotFoundError:
    # not installed, e.g. running tests straight from a checkout
    __version__ = '0.0.0'
