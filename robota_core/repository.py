import datetime
import io
import sys
from abc import abstractmethod
from typing import List, Union

import github
import github.Branch
from github.File import File
import gitlab
import gitlab.v4.objects
import git
from loguru import logger

from robota_core import gitlab_tools, config_readers
from robota_core.commit import CommitCache, Tag, Commit, get_tags_at_date
from robota_core.github_tools import GithubServer
from robota_core.string_processing import string_to_datetime


class Branch:
    """An abstract object representing a git branch.

    :ivar id: Name of branch.
    :ivar id: Commit id that branch points to.
    """
    def __init__(self, branch, source: str):
        self.name = None
        self.id = None

        if source == "gitlab":
            self._branch_from_gitlab(branch)
        elif source == "github":
            self._branch_from_github(branch)
        elif source == "dict":
            self._branch_from_dict(branch)
        elif source == "local":
            self._branch_from_local(branch)
        else:
            TypeError("Unknown branch type.")

    def _branch_from_gitlab(self, branch: gitlab.v4.objects.ProjectBranch):
        self.name = branch.attributes["name"]
        self.id = branch.attributes["commit"]["id"]

    def _branch_from_dict(self, branch: dict):
        self.name = branch["name"]
        self.id = branch["commit_id"]

    def _branch_from_github(self, branch: github.Branch.Branch):
        self.name = branch.name
        self.id = branch.commit.sha

    def _branch_from_local(self, branch: git.Head):
        self.name = branch.name
        self.id = branch.commit.hexsha


class Event:
    """A repository event.

    :ivar date: The date and time of the event.
    :ivar type: 'deleted', 'pushed to' or 'pushed new'
    :ivar ref_type: The thing the event concerns, 'tag', 'branch', 'commit' etc.
    :ivar ref_name: The name of the thing the event concerns (branch name or tag name)
    :ivar commit_id: A commit id associated with ref
    """
    def __init__(self, event_data):
        self.date = None
        self.type = None
        self.ref_type = None
        self.ref_name = None
        self.commit_id = None
        self.commit_count = None

        if isinstance(event_data, gitlab.v4.objects.ProjectEvent):
            self._event_from_gitlab(event_data)
        elif isinstance(event_data, dict):
            self._event_from_dict(event_data)

    def _event_from_gitlab(self, event_data: gitlab.v4.objects.ProjectEvent):
        self.date = string_to_datetime(event_data.attributes['created_at'])
        self.type = event_data.attributes["action_name"]

        if "push_data" in event_data.attributes:
            push_data = event_data.attributes['push_data']
            self.ref_type = push_data['ref_type']
            self.ref_name = push_data['ref']
            self.commit_count = push_data['commit_count']
            if self.type == "deleted":
                self.commit_id = push_data['commit_from']
            else:
                self.commit_id = push_data['commit_to']

    def _event_from_dict(self, event_data: dict):
        self.date = string_to_datetime(event_data['date'])
        self.type = event_data["type"]

        if "push_data" in event_data:
            push_data = event_data['push_data']
            self.ref_type = push_data['ref_type']
            self.ref_name = push_data['ref_name']
            self.commit_id = push_data['commit_id']
            self.commit_count = push_data['commit_count']


class Diff:
    """A representation of a git diff between two points in time for a single
    file in a git repository."""
    def __init__(self, diff_info, diff_source: str):
        self.old_path: str
        self.new_path: str
        self.new_file: bool
        self.diff: str

        if diff_source == "gitlab":
            self._diff_from_gitlab(diff_info)
        elif diff_source == "github":
            self._diff_from_github(diff_info)
        elif diff_source == "local_repo":
            self._diff_from_local(diff_info)
        else:
            raise TypeError(f"Unknown diff source: '{diff_source}'")

    def _diff_from_gitlab(self, diff_info: dict):
        """Populate a diff using the dictionary of diff information returned by gitlab."""
        self.old_path = diff_info["old_path"]
        self.new_path = diff_info["new_path"]
        self.new_file = diff_info["new_file"]
        self.diff = diff_info["diff"]

    def _diff_from_local(self, diff_info: git.Diff):
        self.old_path = diff_info.a_path
        self.new_path = diff_info.b_path
        self.new_file = diff_info.new_file
        self.diff = diff_info.diff

    def _diff_from_github(self, diff_info: github.File.File):
        self.new_path = diff_info.filename
        if diff_info.previous_filename is None:
            self.old_path = self.new_path
        else:
            self.old_path = diff_info.previous_filename
        if diff_info.status == "added":
            self.new_file = True
        else:
            self.new_file = False
        self.diff = diff_info.patch


class Repository:
    """A place where commits, tags, events, branches and files come from.

    :ivar _branches: A list of Branches associated with this repository.
    :ivar _events: A list of Events associated with this repository.
    :ivar _diffs: A dictionary of cached diffs associated with this repository. They are labelled
      in the form key = point_1 + point_2 where point_1 and point_2 are the commit SHAs or branch
      names that the diff describes.
    """
    def __init__(self, project_url: str):
        self._branches: Union[None, List[Branch]] = None
        self._events: List[Event] = []
        self._diffs = {}
        self._stored_commits: List[CommitCache] = []
        self._tags: List[Tag] = []
        self.project_url = project_url

    @abstractmethod
    def list_files(self, identifier: str) -> List[str]:
        """Returns a list of file paths with file names in a repository. Identifier can be a
        commit or branch name. File paths are relative to the repository root."""
        raise NotImplementedError("Not implemented in base class.")

    def get_branches(self) -> List[Branch]:
        """Get all of the Branches in the repository."""
        if not self._branches:
            self._branches = self._fetch_branches()
        return self._branches

    def get_branch(self, name: str) -> Union[Branch, None]:
        """Get a Branch from the repository by name. If Branch does not exist, return None."""
        if not self._branches:
            self._branches = self._fetch_branches()
        for branch in self._branches:
            if branch.name == name:
                return branch
        return None

    @abstractmethod
    def _fetch_branches(self) -> List[Branch]:
        """Retrieve all branches from the server."""
        raise NotImplementedError("Not implemented in base class.")

    @abstractmethod
    def get_events(self) -> List[Event]:
        """Return a list of Events associated with this repository."""
        raise NotImplementedError("Not implemented in base class.")

    @abstractmethod
    def get_file_contents(self, file_path: str, branch: str = "master") -> Union[bytes, None]:
        """Get the decoded contents of a file from the repository. Works well for text files. Might
        explode for other file types."""
        raise NotImplementedError("Not implemented in base class.")

    @abstractmethod
    def compare(self, point_1: str, point_2: str) -> List[Diff]:
        """Compare the state of the repository at two points in time.
        The points may be branch names, tags or commit ids.
        """
        raise NotImplementedError("Not implemented in base class.")

    def get_commits(self, start: datetime.datetime = None, end: datetime.datetime = None,
                    branch: str = None) -> List[Commit]:
        """Get issues from the issue provider between the start date and end date."""
        cached_commits = self._get_cached_commits(start, end, branch)
        if cached_commits:
            return list(cached_commits.commits)

        new_commits = self._fetch_commits(start, end, branch)
        self._stored_commits.append(CommitCache(start, end, branch, new_commits))
        return new_commits

    def get_commit_by_id(self, commit_id: str) -> Union[Commit, None]:
        """Get a Commit by its unique ID number"""
        if commit_id is None:
            return None

        for cache in self._stored_commits:
            for commit in cache:
                if commit.id.startswith(commit_id):
                    return commit

        new_commit = self._fetch_commit_by_id(commit_id)

        # Add the new commit to a cache of its own.
        fake_date = datetime.datetime.fromtimestamp(1)
        new_cache = CommitCache(fake_date, fake_date, "", [new_commit])
        self._stored_commits.append(new_cache)

        return new_commit

    def get_tags(self):
        """Get all tags from the server."""
        if not self._tags:
            self._tags = self._fetch_tags()
        return self._tags

    def get_tag(self, name: str, deadline: datetime.datetime = None,
                events: List["Event"] = None) -> Union[Tag, None]:
        """Get a git Tag by name.

        :param name: The name of the tag to get.
        :param deadline: If provided, filters tags such that tags are only returned if they
          existed at deadline.
        :param events: Events corresponding to the repository, required if deadline is specified.
        :returns: The Tag if found else returns None.
        """
        if not self._tags:
            self._tags = self._fetch_tags()
        tags_to_search = self._tags

        if deadline:
            if not events:
                raise SyntaxError("Must provide list of events if deadline is specified.")
            tags_to_search = get_tags_at_date(deadline, tags_to_search, events)

        for tag in tags_to_search:
            if tag.name == name:
                return tag
        return None

    def _get_cached_commits(self, start: datetime.datetime,
                            end: datetime.datetime, branch: str) -> Union[CommitCache, None]:
        """Check whether commits with the specified start, end and branch are already stored."""
        for cache in self._stored_commits:
            if cache.start == start and cache.end == end and cache.branch == branch:
                return cache
        return None

    @abstractmethod
    def _fetch_tags(self) -> List[Tag]:
        """Fetch tags from a the server."""
        raise NotImplementedError("Not implemented in base class.")

    @abstractmethod
    def _fetch_commit_by_id(self, commit_id: str) -> Union[Commit, None]:
        """Fetch a single commit from the server."""
        raise NotImplementedError("Not implemented in base class.")

    @abstractmethod
    def _fetch_commits(self, start: Union[datetime.datetime, None],
                       end: Union[datetime.datetime, None],
                       branch: Union[str, None]) -> List[Commit]:
        """Fetch a list of commits from the server."""
        raise NotImplementedError("Not implemented in base class.")


class LocalRepository(Repository):

    def __init__(self, commit_source: dict):
        super().__init__(commit_source["path"])
        self.repo = git.Repo(commit_source["path"])

    def list_files(self, identifier: str) -> List[str]:
        files = self.repo.tree(identifier).traverse()
        file_paths = [file.path for file in files if file.type == "blob"]
        return file_paths

    def get_file_contents(self, file_path: str, branch: str = "master") -> Union[bytes, None]:
        file = self.repo.heads[branch].commit.tree / file_path

        with io.BytesIO(file.data_stream.read()) as f:
            return f.read()

    def compare(self, point_1: str, point_2: str) -> List[Diff]:
        commit_1 = self._get_commit(point_1)
        commit_2 = self._get_commit(point_2)
        diffs = commit_1.diff(commit_2, create_patch=True)
        robota_diffs = [Diff(diff, "local_repo") for diff in diffs]
        return robota_diffs

    def _get_commit(self, ref: str) -> git.Commit:
        """Get a commit object from a ref which is a branch, tag or commit SHA."""
        try:
            commit = self.repo.heads[ref].commit
            return commit
        except IndexError:
            pass
        try:
            commit = self.repo.tags[ref].commit
            return commit
        except IndexError:
            pass
        try:
            commit = self.repo.commit(ref)
            return commit
        except IndexError:
            logger.error(f"Can't find object {ref} in Local repository. Object must be branch name,"
                         f"tag or commit SHA.")
            sys.exit(1)

    def get_events(self) -> List[Event]:
        # TODO: Can events be mined from the reflog?
        raise NotImplementedError("Get events not implemented for LocalRepository")

    def _fetch_branches(self) -> List[Branch]:
        return [Branch(branch, "local") for branch in self.repo.branches]

    def _fetch_commits(self, start: Union[datetime.datetime, None],
                       end: Union[datetime.datetime, None],
                       branch: Union[str, None]) -> List[Commit]:
        rev_list_args = {}
        if start:
            rev_list_args["since"] = start.isoformat()
        if end:
            rev_list_args["until"] = end.isoformat()
        rev = None
        if branch:
            rev = branch
        commits = self.repo.iter_commits(rev, "", **rev_list_args)
        return [Commit(commit, "local") for commit in commits]

    def _fetch_commit_by_id(self, commit_id: str) -> Union[Commit, None]:
        return Commit(self.repo.commit(commit_id), "local")

    def _fetch_tags(self) -> List[Tag]:
        return [Tag(tag, "local") for tag in self.repo.tags]


class GithubRepository(Repository):
    def __init__(self, repository_source: dict):
        super().__init__(repository_source['url'])
        server = GithubServer(repository_source)
        self.repo = server.open_github_repo(repository_source["project"])

    def list_files(self, identifier: str) -> List[str]:
        files = self.repo.get_git_tree(identifier, recursive=True)
        file_paths = [file.path for file in files.tree if file.type == "blob"]
        return file_paths

    def _fetch_branches(self) -> List[Branch]:
        return [Branch(branch, "github") for branch in self.repo.get_branches()]

    def get_events(self) -> List[Event]:
        raise NotImplementedError("Method not implemented for Github Repository")

    def get_file_contents(self, file_path: str, branch: str = "master") -> Union[bytes, None]:
        try:
            file = self.repo.get_contents(file_path, branch)
        except github.UnknownObjectException:
            return None
        return file.decoded_content

    def compare(self, point_1: str, point_2: str) -> List[Diff]:
        comparison = self.repo.compare(point_1, point_2)
        return [Diff(diff, "github") for diff in comparison.files]

    def _fetch_commit_by_id(self, commit_id: str) -> Union[Commit, None]:
        try:
            commit_data = self.repo.get_commit(commit_id)
        except github.GithubException as e:
            if e.status == 422:
                return None
            else:
                raise e

        return Commit(commit_data, "github")

    def _fetch_commits(self, start: Union[datetime.datetime, None],
                       end: Union[datetime.datetime, None],
                       branch: Union[str, None]) -> List[Commit]:
        if not start:
            start = github.GithubObject.NotSet
        if not end:
            end = github.GithubObject.NotSet
        if not branch:
            branch = github.GithubObject.NotSet

        github_commits = self.repo.get_commits(sha=branch, since=start, until=end)
        return [Commit(github_commit, "github") for github_commit in github_commits]

    def _fetch_tags(self) -> List[Tag]:
        github_tags = self.repo.get_tags()
        return [Tag(github_tag, "github") for github_tag in github_tags]


class GitlabRepository(Repository):
    """A Gitlab flavour of a repository.

    :ivar project: A connection to the gitlab repository
    """

    def __init__(self, data_source: dict):
        if "token" in data_source:
            token = data_source["token"]
        else:
            token = None
        server = gitlab_tools.GitlabServer(data_source["url"], token)
        self.project = server.open_gitlab_project(data_source["project"])

        super().__init__(self.project.attributes["web_url"])

    def list_files(self, identifier: str) -> List[str]:
        files = []
        page_num = 1
        while True:
            file_page = self.project.repository_tree(ref=identifier, per_page=100, page=page_num,
                                                     recursive=True)
            if file_page:
                files.extend(file_page)
                page_num += 1
            else:
                break
        file_paths = [file["path"] for file in files if file["type"] == "blob"]
        return file_paths

    def _fetch_branches(self) -> List[Branch]:
        return [Branch(branch, "gitlab") for branch in self.project.branches.list(all=True)]

    def get_events(self) -> List[Event]:
        """Return a list of Events associated with this repository."""
        if not self._events:
            # API requires date in ISO 8601 format
            gitlab_events = self.project.events.list(all=True, action="pushed")

            for gitlab_event in gitlab_events:
                self._events.append(Event(gitlab_event))
        return self._events

    def get_file_contents(self, file_path: str, branch: str = "master") -> Union[bytes, None]:
        """Get a file directly from the repository."""
        try:
            file = self.project.files.get(file_path, branch)
        except gitlab.GitlabGetError:
            return None
        else:
            return file.decode()

    def compare(self, point_1: str, point_2: str) -> List[Diff]:
        """Compare the state of the repository at two points in time.
        The points may be branch names, tags or commit ids.
        Point 1 must be chronologically before point 2.
        """
        if not point_1 + point_2 in self._diffs:
            gitlab_diffs = self.project.repository_compare(point_1, point_2)
            robota_diffs = [Diff(diff, "gitlab") for diff in gitlab_diffs["diffs"]]
            self._diffs[point_1 + point_2] = robota_diffs

        return self._diffs[point_1 + point_2]

    def _fetch_commits(self, start: Union[datetime.datetime, None],
                       end: Union[datetime.datetime, None],
                       branch: Union[str, None]) -> List[Commit]:
        """ Function to return commits falling withing a certain time window.

        :param start: The start of the time window for included commits.
        :param end: The end of the time window for included commits.
        :param branch: Filters commits by branch name. If None, get commits from all branches.
        :return: A list of Commit object.
        """
        request_parameters = {}

        if start is not None:
            request_parameters['since'] = start.isoformat()

        if end is not None:
            request_parameters['until'] = end.isoformat()

        if branch is None:
            request_parameters['all'] = True
        else:
            request_parameters['ref_name'] = branch

        gitlab_commits = self.project.commits.list(all=True,
                                                   query_parameters=request_parameters)

        return [Commit(commit,  "gitlab", self.project_url) for commit in gitlab_commits]

    def _fetch_commit_by_id(self, commit_id: str) -> Union[Commit, None]:
        try:
            gitlab_commit = self.project.commits.get(commit_id)
        except gitlab.exceptions.GitlabGetError:
            return None

        return Commit(gitlab_commit, "gitlab", self.project_url)

    def _fetch_tags(self) -> List[Tag]:
        """Method for getting tags from the gitlab server."""
        gitlab_tags = self.project.tags.list(all=True)
        return [Tag(gitlab_tag, "gitlab") for gitlab_tag in gitlab_tags]


def new_repository(robota_config: dict) -> Union[Repository, None]:
    """Factory method for Repositories."""
    repo_config = config_readers.get_data_source_info(robota_config, "repository")
    if not repo_config:
        return None
    repo_type = repo_config["type"]

    logger.debug(f"Initialising {repo_type} repository.")

    if repo_type == "gitlab":
        return GitlabRepository(repo_config)
    elif repo_type == "github":
        return GithubRepository(repo_config)
    elif repo_type == 'local_repository':
        return LocalRepository(repo_config)
    else:
        raise TypeError(f"Unknown repository type {repo_config['type']}.")
