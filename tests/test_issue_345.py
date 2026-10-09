import unittest

from redbeat import RedBeatSchedulerEntry
from tests.basecase import RedBeatCase


class test_Issue_345(RedBeatCase):
    """generate_key() reads app.redbeat_conf without calling ensure_conf().

    https://github.com/sibson/redbeat/issues/345

    Expected: generate_key() on a fresh app returns '<key_prefix><name>'.
    Actual:   AttributeError: 'Celery' object has no attribute 'redbeat_conf'.

    TRIAGE ARTIFACT -- this file is temporary. When the fix lands, move this
    test into tests/test_entry.py::test_RedBeatEntry, drop the
    expectedFailure marker, rename it for the behaviour it checks rather
    than the issue number, and delete this file.
    """

    @unittest.expectedFailure
    def test_generate_key_initialises_conf(self):
        self.assertFalse(hasattr(self.app, 'redbeat_conf'))

        key = RedBeatSchedulerEntry.generate_key(self.app, 'my-task')

        self.assertEqual(key, 'rb-tests:my-task')
