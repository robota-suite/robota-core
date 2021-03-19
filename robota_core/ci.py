"""
Module that defines interactions with a Continuous integration server in order to get
build information.
"""
import json
from loguru import logger
from datetime import datetime
from enum import Enum
from typing import Union, List, Dict, TypeVar
from abc import ABC, abstractmethod

import jenkins
import requests

from robota_core.string_processing import string_to_datetime, get_link
from robota_core import config_readers


class Test:
    """A representation of the result of a Test.

    :ivar name: The name of the test.
    :ivar result: The result of the test, PASSED or FAILED.
    :ivar time: The time that the test ran.
    :ivar branch: The branch of commit the test was run upon. This is not populated on object
      creation."""
    def __init__(self, suite: dict, case: dict):
        self.name = f"{suite['name']}.{case['name']}"
        self.result = case["status"]
        self.time = string_to_datetime(suite["timestamp"], "%Y-%m-%dT%H:%M:%S")
        self.branch = None

    def __eq__(self, test_result: "Test"):
        if self.name == test_result.name:
            return True
        return False

    def __hash__(self):
        return hash(self.name)


class BuildResult(Enum):
    """Represents the result of a Jenkins build."""
    Success = 1
    Unstable = 2
    Failure = 3
    Aborted = 4
    Not_Built = 5
    Gitlab_Timeout = 6

    def __str__(self):
        return self.name


class Build:
    """A Build is the result of executing a CI job.

    :ivar number: The number of the build.
    :ivar result: The result of the build
    :ivar timestamp: The time at which the build started.
    :ivar commit_id: The ID of the git commit the build was run on.
    :ivar branch_name: The git branch of the commit the build was run on.
    :ivar link: A HTML string linking to the web-page that displays the build on Jenkins.
    :ivar instruction_coverage: A code coverage result from JaCoCo.
    """
    def __init__(self, jenkins_build):
        self.number: str = ""
        self.result: BuildResult = None
        self.timestamp: datetime = None
        self.commit_id: str = ""
        self.branch_name: str = ""
        self.link: str = ""
        self.instruction_coverage: dict = {}
        self.test_coverage_url: str = ""

        self.build_from_jenkins(jenkins_build)

    def build_from_jenkins(self, jenkins_build):
        """Create a Robota Build object from a Jenkins build object."""
        self.number = jenkins_build["number"]
        self.result = self._assign_build_result(jenkins_build["result"])
        self.timestamp = datetime.fromtimestamp(jenkins_build["timestamp"] / 1000)
        self.link = get_link(jenkins_build["url"], self.result.name)
        self.test_coverage_url = f'{jenkins_build["url"]}jacoco/'
        for action in jenkins_build["actions"]:
            if "_class" in action:
                if action["_class"] == "hudson.plugins.git.util.BuildData":
                    self.commit_id = action["lastBuiltRevision"]["SHA1"]
                    self.branch_name = action["lastBuiltRevision"]["branch"][0]["name"]
                if action["_class"] == "hudson.plugins.jacoco.JacocoBuildAction":
                    if "instructionCoverage" in action:
                        self.instruction_coverage = action['instructionCoverage']
                if "FailureCauseBuildAction" in action["_class"]:
                    for cause in action["foundFailureCauses"]:
                        if cause["name"] == 'Connection time-out while accessing GitLab':
                            self.result = BuildResult.Gitlab_Timeout

    @staticmethod
    def _assign_build_result(build_result: str) -> BuildResult:
        """Convert the build result string from Jenkins into a BuildResult representation."""
        if build_result == "SUCCESS":
            return BuildResult.Success
        elif build_result == "UNSTABLE":
            return BuildResult.Unstable
        elif build_result == "FAILURE":
            return BuildResult.Failure
        elif build_result == "ABORTED":
            return BuildResult.Aborted
        elif build_result == "NOT_BUILT" or build_result is None:
            return BuildResult.Failure
        else:
            raise KeyError(f"Build result of type {build_result} not known.")


class Job:
    """A job is a series of CI checks. Each time a job is executed it stores
    the result in a build.
    """
    def __init__(self, job_data, project_root):
        self.name = None
        self.short_name = None
        self.url = None
        # Builds are ordered most recent first.
        self.last_build_number = None
        self.last_completed_build_number = None
        self.last_successful_build_number = None
        self._builds: List[Build] = []

        self.job_from_jenkins(job_data, project_root)

    def job_from_jenkins(self, jenkins_job: dict, project_root: str):
        """Create a Robota Job object from a Jenkins Job object."""
        self.name = jenkins_job["fullName"].replace(project_root + "/", "")
        self.short_name = jenkins_job["name"]
        self.url = jenkins_job["url"]
        if jenkins_job["lastBuild"]:
            self.last_build_number = jenkins_job["lastBuild"]["number"]
        if jenkins_job["lastCompletedBuild"]:
            self.last_completed_build_number = jenkins_job["lastCompletedBuild"]["number"]
        if jenkins_job["lastSuccessfulBuild"]:
            self.last_successful_build_number = jenkins_job["lastSuccessfulBuild"]["number"]

        for jenkins_build in jenkins_job["builds"]:
            self._builds.append(Build(jenkins_build))

    def get_builds(self) -> List[Build]:
        """Get all builds of a job."""
        return self._builds

    def get_build_by_number(self, number) -> Union[Build, None]:
        """Get build of this job by number, where 1 is the chronologically earliest build of a job.
        If build is not found, returns None."""
        for build in self._builds:
            if build.number == number:
                return build
        return None

    def get_last_completed_build(self) -> Union[Build, None]:
        """"Get the last completed build of a job."""
        try:
            return self.get_build_by_number(self.last_completed_build_number)
        except AttributeError:
            return None

    def get_last_build(self, start: datetime, end: datetime) -> Union[None, Build]:
        """Get most recent job build status between start and end.

        :param start: Build must occur after this time
        :param end: Build must occur before this time
        :return: Last build in time window, None if no job in time window.
        """
        if start is None or end is None:
            raise TypeError

        # Start with most recent build, looking for the last build before *end*
        builds = self.get_builds()
        for build in builds:
            if start < build.timestamp < end:
                return build
        return None

    def get_first_successful_build(self, start: datetime, end: datetime) -> Union[None, Build]:
        """Return the first (oldest) successful build in the time window."""
        for build in reversed(self.get_builds()):
            if start < build.timestamp < end and build.result == BuildResult.Success:
                return build
        return None

    def get_first_build(self, start: datetime, end: datetime) -> Union[None, Build]:
        """Return the first (oldest) build in the time window."""
        for build in reversed(self.get_builds()):
            if start < build.timestamp < end:
                return build
        return None

    def get_build_by_commit_id(self, commit_id) -> Union[Build, None]:
        """Get a job triggered by commit_id"""
        builds = self.get_builds()
        for build in builds:
            if commit_id == build.commit_id:
                return build
        return None


class CIServer(ABC):
    """A CIServer is a service from which test results are fetched. All of these are abstract
    methods implemented by subclasses.
    """
    def __init__(self):
        self._jobs: List[Job] = []
        self.tests: Dict[str, List[Test]] = {}

    @abstractmethod
    def get_jobs_by_folder(self, folder_name: str) -> List[Job]:
        """Get all jobs located in a particular folder."""
        raise NotImplementedError("Not implemented in base class.")

    @abstractmethod
    def get_job_by_name(self, job_name: str) -> Union[Job, None]:
        """Get a job by its name. Return None if job not found."""
        raise NotImplementedError("Not implemented in base class.")

    @abstractmethod
    def get_tests(self, job_path: str) -> Union[None, List[Test]]:
        """Get all Tests that were run for a job."""
        raise NotImplementedError("Not implemented in base class.")

    @abstractmethod
    def get_package_coverage(self, job_path: str, package_name: str) -> Union[None, float]:
        """Get the percentage test coverage for a particular package."""
        raise NotImplementedError("Not implemented in base class.")


class JenkinsCIServer(CIServer):
    """With Jenkins it is possible to download all of the jobs from a whole project at once.
    This is much quicker than getting each job one by one as the API requests are slow. For this
    reason the JenkinsCIServer class downloads all jobs from a project and then helper methods
    get jobs from the local cache."""
    def __init__(self, ci_source: dict):
        """Connects to Jenkins and downloads all jobs. If the jobs are heavily nested in folders,
        it may be necessary to increase the depth parameter to iteratively fetch the lower level
        jobs.

        :param ci_source: A dictionary of config info for setting up the JenkinsCIServer.
        """
        super().__init__()
        self.url = ci_source["url"]
        token = ci_source["token"]
        username = ci_source["username"]

        self.project_name = ci_source["project_name"]
        self.folder_name = ci_source["folder_name"]
        self.base_request_string = f"{self.url}job/{self.project_name}/job/{self.folder_name}/"

        logger.info("Logging in to Jenkins to get CI information.")
        self.server = jenkins.Jenkins(self.url, username=username, password=token)

        # Populate the CIServer object with Jobs
        request_string = self._build_request_string(folder_depth=4)
        job_data = self.server.jenkins_open(requests.Request('GET', request_string))
        all_jobs = json.loads(job_data)
        self._populate_jobs(all_jobs)

    def _populate_jobs(self, nested_jobs):
        """Iteratively unfolds jobs from any containing folders, and stores all jobs as a
        flat list."""
        for child in nested_jobs["jobs"]:
            if child["_class"].endswith("Folder"):
                self._populate_jobs(child)
            else:
                self._add_job(child)

    def _add_job(self, jenkins_job: dict):
        """Adds a single job to the list of jobs in the CIJobServer instance."""
        self._jobs.append(Job(jenkins_job, f"{self.project_name}/{self.folder_name}"))

    def get_jobs_by_folder(self, folder_name: str) -> List[Job]:
        """Get all jobs that were located in a particular folder."""
        jobs = []
        for job in self._jobs:
            if job.name.startswith(folder_name):
                jobs.append(job)
        return jobs

    def get_job_by_name(self, job_name: str) -> Union[Job, None]:
        """Get a job by its name. Return None if job not found."""
        for job in self._jobs:
            if job.name == job_name:
                return job
        return None

    def _build_request_string(self, folder_depth=4) -> str:
        """Returns the request string for all of the Jenkins build results in a folder.
        The string is formed recursively since the jobs may be in nested folders.

        :param folder_depth: The number of folders deep to nest the xtree request.
        """
        jobs = "jobs[fullName,name,url,lastBuild[number],lastCompletedBuild[number]," \
               "lastSuccessfulBuild[number],BUILDS,JOBS]"
        builds = "builds[number,result,timestamp,url,actions" \
                 "[_class,lastBuiltRevision[SHA1,branch[*]],instructionCoverage[*]," \
                 "foundFailureCauses[*]]]"

        tree_string = jobs

        for i in range(folder_depth):
            tree_string = tree_string.replace("JOBS", jobs)
            if i == (folder_depth - 1):
                tree_string = tree_string.replace(",JOBS", "")
        tree_string = tree_string.replace("BUILDS", builds)
        return f"{self.base_request_string}/api/json?depth={folder_depth}&tree={tree_string}"

    def get_tests(self, job_path: str) -> Union[None, List[Test]]:
        """Get Tests for a job - this is a separate API request to the main job info."""
        if job_path in self.tests:
            return self.tests[job_path]

        job_name = job_path.replace('/', '/job/')
        job_name = f'job/{job_name}'
        request_string = f"{self.base_request_string}{job_name}/lastCompletedBuild/testReport/" \
                         f"api/json?tree=suites[cases[name,status],name,timestamp]"
        response = self._jenkins_get(request_string)
        if not response:
            return None
        data = json.loads(response)
        tests = self._process_test_names(data)
        self.tests[job_path] = tests

        return tests

    def get_package_coverage(self, job_path: str, package_name: str) -> Union[None, float]:
        """Get the percentage test coverage for a particular package.

        :param job_path: The tag or job name to query.
        :param package_name: The name of the package to get coverage for.
        """
        job_name = job_path.replace('/', '/job/')
        job_name = f'job/{job_name}'
        request_string = f"{self.base_request_string}{job_name}/lastCompletedBuild/jacoco/" \
                         f"{package_name}/api/json?tree=instructionCoverage[percentageFloat]"
        response = self._jenkins_get(request_string)
        if response is None:
            return None
        coverage = json.loads(response)
        return coverage["instructionCoverage"]["percentageFloat"]

    def _jenkins_get(self, request_string: str) -> Union[None, str]:
        """Send a direct API request to the open Jenkins server.

        :param request_string: The API request string to send.
        """
        request = requests.Request('GET', request_string)
        try:
            response = self.server.jenkins_open(request)
        except jenkins.NotFoundException:
            # If the job has not generated data corresponding to the request string
            # then the API request will fail.
            return None
        return response

    @staticmethod
    def _process_test_names(data: dict) -> List[Test]:
        """Get a list of test names from the nested JSON in the test report."""
        tests = []
        for suite in data["suites"]:
            for case in suite["cases"]:
                tests.append(Test(suite, case))
        return tests


# This type refers to any of the subclasses of CIServer - it is used for typing the return of the
# CIServer factory method.
CIType = TypeVar('CIType', bound=CIServer)


def new_ci_server(robota_config: dict) -> Union[None, CIType]:
    """Factory method for creating CIServers"""
    ci_server_source = config_readers.get_data_source_info(robota_config, 'ci')
    if not ci_server_source:
        return None
    ci_type = ci_server_source["type"]

    logger.debug(f"Initialising {ci_type} ci server.")

    if ci_server_source["type"] == 'jenkins':
        return JenkinsCIServer(ci_server_source)
    else:
        raise TypeError(f"Unknown CI server type {ci_server_source['type']}.")
