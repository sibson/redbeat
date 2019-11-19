from celery.utils.time import maybe_make_aware

from basecase import RedBeatCase
from redbeat.schedulers import to_timestamp, from_timestamp


class Test_utils(RedBeatCase):

    def test_roundtrip(self):
        now = self.app.now()
        # 3.x returns naive, but 4.x returns aware
        now = maybe_make_aware(now)

        roundtripped = from_timestamp(to_timestamp(now))

        # we lose microseconds in the roundtrip, so we need to ignore them
        now = now.replace(microsecond=0)

        self.assertEqual(now, roundtripped)
