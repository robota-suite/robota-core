import unittest
from datetime import datetime, timezone

from robota_core.string_processing import string_to_datetime


class TestStringProcessing(unittest.TestCase):

    def test_string_to_datetime_with_format_given(self):
        self.assertEqual(string_to_datetime('2017-12-06T08:28:32.000Z', '%Y-%m-%dT%H:%M:%S.%fZ'),
                         datetime(2017, 12, 6, 8, 28, 32, tzinfo=timezone.utc))

    def test_string_to_datetime_with_no_format(self):
        self.assertEqual(string_to_datetime('2017-11-10T09:08:07.000+00:00'),
                         datetime(2017, 11, 10, 9, 8, 7, tzinfo=timezone.utc))

    def test_string_to_datetime_when_no_string_given(self):
        self.assertEqual(string_to_datetime(None, '%Y-%m-%d'), None)
