"""A module to collect statistics on student attendance."""
import json
from loguru import logger
import time

import requests

from robota_core import config_readers


class AttendanceError(Exception):
    """An error in collecting attendance data."""


class StudentAttendance:
    """The student attendance class collects data from an external API about student attendance."""

    def __init__(self, robota_config: dict, mock: bool = False):
        """
        :param robota_config: A dictionary of information about data sources read from the robota
          config file.
        :param mock: If True, return mock data instead of getting real data from the data source.
        """
        data_source_name = "attendance"
        attendance_source = config_readers.get_data_source_info(robota_config, data_source_name)
        if not attendance_source:
            raise KeyError(f"Data source '{data_source_name}' not found in robota config.")
        self.data = None
        self.mock = mock
        self._get_course_attendance(attendance_source)
        self.total_sessions = self._get_number_of_sessions()

    def _get_course_attendance(self, attendance_source: dict):
        """Get student attendance using the specified data source.

        :param attendance_source: Information about where to get attendance data from.
        """
        if self.mock:
            logger.warning("Attendance mocking specified - providing mocked attendance data.")
            return

        if attendance_source["type"] == "benchmark":
            logger.info("Connecting to Benchmark to retrieve attendance data.")
            self._get_benchmark_attendance(attendance_source)
        else:
            raise KeyError(f"Student attendance of type: "
                           f"{attendance_source['type']} not implemented.")

    def _get_benchmark_attendance(self, attendance_source: dict):
        """Collect data from the UoM CS Benchmark API. To simplify the API requests, all
        of the attendance data for a particular course is downloaded at once. This means that
        StudentAttendance should be instantiated at the beginning and then data collected
        student by student by accessing the process_benchmark_data method.

        :param attendance_source: Information about where to get attendance data from.
        """
        headers = {'Private-Token': attendance_source["token"]}
        data = requests.get(attendance_source["url"], headers=headers).text
        self.data = json.loads(data)

    def get_student_attendance(self, student_id: str) -> int:
        """For an individual student, get their attendance from the list of all attendances.

        :param student_id: The university ID name of the student to get attendance of.
        :return student_attendance: The number of sessions attended in the current year.
        """
        if self.mock:
            return 8

        student_attendance = 0
        current_time = time.time()
        for week in self.data:
            # Only collect attendance data for weeks that have passed.
            if week["finish"] < current_time:
                try:
                    if week["events"][student_id][0]["data"] == "present":
                        student_attendance += 1
                except KeyError:
                    pass
        return student_attendance

    def _get_number_of_sessions(self) -> int:
        """Get the total number of sessions that a student could have attended in the
        current year."""

        if self.mock:
            return 10
        else:
            num_sessions = 0
            current_time = time.time()
            for week in self.data:
                if week["finish"] < current_time:
                    num_sessions += 1
            return num_sessions
