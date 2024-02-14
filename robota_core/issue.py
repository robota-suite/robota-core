"""Objects and for describing and processing Git Issues."""
from abc import abstractmethod
import datetime
from operator import attrgetter
from typing import List, Union, Tuple
import re

import github.Issue
import github.IssueComment
from gitlab.v4.objects import ProjectIssueNote, ProjectIssue
from loguru import logger

from robota_core import gitlab_tools, config_readers
from robota_core.github_tools import GithubServer
from robota_core.string_processing import string_to_datetime, get_link, clean


class Issue:
    """An Issue

    :ivar created_at: (datetime) The time at which the issue was created.
    :ivar assignee: (string) The person to whom the issue was assigned.
    :ivar closed_at: (datetime) The time at which the issue was closed.
    :ivar closed_by: (string) The person who closed the issue.
    :ivar time_stats: (dict) Estimates and reported time taken to work on the issue.
    :ivar due_date: (datetime) The time at which issue is due to be completed.
    :ivar title: (string) The title of the issue.
    :ivar comments: (List[Comment]) A list of Comments associated with the Issue.
    :ivar state: (string) Whether the issue is open or closed.
    :ivar milestone: (string) Any milestone the issue is associated with.
    :ivar url: (string) A link to the Issue on GitLab.

    """
    def __init__(self, issue, issue_source: str, get_comments=True):
        self.created_at = None
        self.assignee = None
        self.closed_at = None
        self.closed_by = None
        self.time_stats = None
        self.due_date = None
        self.title = ""
        self.comments: List[IssueComment] = []
        self.state = None
        self.milestone = None
        self.url = ""
        self.number = None

        if issue_source == "gitlab":
            self._issue_from_gitlab(issue, get_comments)
        elif issue_source == "github":
            self._issue_from_github(issue, get_comments)
        elif issue_source == "test data":
            self._issue_from_test_data(issue)
        else:
            raise TypeError(f"Unknown issue type: '{issue_source}'")

        self.link = get_link(self.url, self.title)

    def __eq__(self, other_issue: Union[None, "Issue"]) -> bool:
        if other_issue is None:
            return False
        elif self.created_at == other_issue.created_at and self.title == other_issue.title:
            return True
        else:
            return False

    def __repr__(self) -> str:
        return f"Issue: {self.title}"

    def _issue_from_github(self, github_issue: github.Issue.Issue, get_comments: bool):
        self.created_at = github_issue.created_at
        if github_issue.assignee:
            self.assignee = github_issue.assignee.name
        else:
            self.assignee = None
        if github_issue.closed_by:
            self.closed_by = github_issue.closed_by.name
        else:
            self.closed_by = None
        self.title = github_issue.title
        self.state = github_issue.state
        if github_issue.milestone:
            self.milestone = {"title": github_issue.milestone.title,
                              'web_url': github_issue.milestone.url}
        else:
            self.milestone = None
        self.url = github_issue.html_url
        self.number = github_issue.number
        if get_comments:
            comments = github_issue.get_comments()
            for comment in comments:
                self.comments.append(IssueComment(comment, "github"))

    def _issue_from_gitlab(self, gitlab_issue: ProjectIssue, get_comments: bool):
        """Convert a GitLabIssue to a RoboTA issue."""
        self.created_at = string_to_datetime(gitlab_issue.attributes["created_at"])
        self.assignee = gitlab_issue.attributes["assignee"]
        self.closed_at = string_to_datetime(gitlab_issue.attributes["closed_at"])
        self.closed_by = gitlab_issue.attributes["closed_by"]
        self.time_stats = gitlab_issue.attributes["time_stats"]
        self.due_date = string_to_datetime(gitlab_issue.attributes["due_date"], '%Y-%m-%d')
        self.title = gitlab_issue.attributes["title"]
        if gitlab_issue.state == "opened":
            self.state = "open"
        else:
            self.state = gitlab_issue.state
        gitlab_milestone = gitlab_issue.attributes["milestone"]
        if gitlab_milestone:
            self.milestone = {"title": gitlab_milestone['title'],
                              'web_url': gitlab_milestone['web_url']}

        self.url = gitlab_issue.attributes["web_url"]
        self.number = gitlab_issue.attributes["iid"]
        if get_comments:
            all_notes = gitlab_issue.notes.list(all=True)
            for note in all_notes:
                self.comments.append(IssueComment(note, "gitlab"))

            # Convert the issue state events into comments (since GitLab now handles these events separately
            # and does not create a comment on the issue when its state changes.
            all_state_events = gitlab_issue.resourcestateevents.list(all=True)
            for state_change in all_state_events:
                state_change_occurred_at = string_to_datetime(state_change.created_at)
                note = (state_change.state, state_change_occurred_at, state_change_occurred_at, True, state_change.user["username"])
                self.comments.append(IssueComment(note, "test data"))

        # Returns comments in descending order of creation date (oldest first)
        self.comments.sort(key=attrgetter("created_at"))


    def _issue_from_test_data(self, issue_data):
        (number, title) = issue_data
        self.number = number
        self.title = title

    def get_assignee(self) -> Union[str, None]:
        """ Return name of issue assignee

        :return If issue has an assignee, returns their name else returns None.
        """
        if self.assignee:
            return self.assignee['name']
        return None

    def get_assignment_date(self) -> Union[datetime.datetime, None]:
        """Get assignment date for an issue.
        First checks comments for assignment date and if none is found, returns the issue creation
        date. If there is more than one assignment date, this method will always return the most
        recent.

        :return: The date at which the issue was assigned.
        """
        if not self.assignee:
            return None

        # Looking for most recent comment first so reverse comment list.
        for comment in reversed(self.comments):
            if comment.text.startswith('assigned to'):
                return comment.created_at
        return self.created_at

    def get_time_estimate_date(self) -> Union[datetime.datetime, None]:
        """Gets the date a time estimate was added to an issue. This only works for issues
        made after 05/02/19 as this was a feature added in Gitlab 11.4.

        :return: Date of the first time estimate, None if no time estimate was found.
        """
        # Comments are stored oldest first.
        for comment in reversed(self.comments):
            if comment.text.startswith('changed time estimate to'):
                return comment.created_at
        return None

    def get_time_estimate(self) -> datetime.timedelta:
        """Gets estimate of time it will take to close issue."""
        time_estimate = self.time_stats['time_estimate']
        return datetime.timedelta(seconds=time_estimate)

    def get_comment_timestamp(self, key_phrase: str,
                              earliest=False) -> Union[datetime.datetime, None]:
        """Search for a phrase in the comments of an issue
        If the phrase exists, return creation time of the comment.

        :param key_phrase: a phrase to search for in a comment on the issue.
        :param earliest: If True, return the earliest comment matching key_phrase, else return
          most recent comment matching key_phrase.
        :return: If phrase is present in a comment, return the the time of the comment,
          else return None
        """
        # Since we can't guarantee that all Git hosting sites will return comments in the same order
        # we specifically search for the one we want
        comments = self.comments

        matching_comments = [c.created_at for c in comments if key_phrase in c.text]
        if matching_comments:
            matching_comments.sort(reverse=not earliest)
            return matching_comments[0]
        return None

    def get_recorded_team_member(self, key_phrase: str) -> Union[None, List[str]]:
        """Report whether a team member has been recorded using a key phrase for issue.
        Key phrase should appear at the start of a comment to indicate assignment of sub-team
        member, code reviewer (etc).

        :param key_phrase: Phrase to search for
        :return team_member_recorded: Str
        """

        # Strings we're searching for are:
        # - key_phrase @username
        # - key_phrase https://gitlab.cs.man.ac.uk/username
        # - key_phrase https://gitlab.cs.man.ac.uk/user.name
        # - key_phrase https://gitlab.cs.man.ac.uk/user-name
        # Also permit the team member to be quoted or in angle brackets
        # Also permit the url to be in square brackets as this is markdown for a link
        regex = r"\s*(<|\"|\'|\[)*(@|https:\/\/gitlab\.cs\.man\.ac\.uk\/)(\w+[-\.]?\w*)(>|\"|\'|\])*"
        regex = key_phrase + regex
        recorded_team_member = []
        for comment in self.comments:
            match = re.findall(regex, comment.text)
            if match:
                for match_contents in match:
                    recorded_team_member.append(match_contents[2])

        if recorded_team_member:
            return recorded_team_member
        return None

    def is_assignee_contributing(self, team) -> Union[bool, str]:
        """Determine whether the Student assigned to work on an Issue is contributing to the
        exercise."""
        if self.assignee is None:
            return "No issue assignee."
        else:
            assigned_student = team.get_student_by_name(self.assignee["name"])
            if assigned_student is None:
                # This will happen if a student leaves the team after the exercise.
                return "Assignee is not a team member"
            else:
                return assigned_student.is_contributing

    def get_status(self, deadline: datetime.datetime):
        """Get current status of issue if deadline hasn't passed,
        otherwise get last status of issue before the deadline,
        and save in the issue.state attribute so that it is only calculated once.

        :param deadline:
        :return:
        """
        if datetime.datetime.now() < deadline:
            return self.state
        else:
            for comment in self.comments:
                # Has the issue status changed since the deadline?
                if comment.system and comment.created_at < deadline:
                    if comment.text.startswith('closed'):
                        self.state = 'closed'
                        break
                    elif comment.text == 'reopened':
                        self.state = 'open'
                        break
            else:
                # No status change before the deadline
                self.state = 'open'

            return self.state


class IssueCache:
    """A cache of Issue objects from a specific date range."""
    def __init__(self, start: datetime.datetime = None, end: datetime.datetime = None,
                 get_comments=True, milestone=None):
        self.start = start
        self.end = end
        self.get_comments = get_comments
        self.issues: List[Issue] = []
        self.milestone = milestone

    def __iter__(self):
        yield from self.issues

    def add_issue(self, issue: Issue):
        """Add an Issue to an IssueCache."""
        self.issues.append(issue)


class IssueServer:
    """An IssueServer is a service from which Issues are extracted."""
    def __init__(self):
        self._stored_issues: List[IssueCache] = []

    def get_issues(self, start: datetime.datetime = datetime.datetime.fromtimestamp(1),
                   end: datetime.datetime = datetime.datetime.now(),
                   get_comments: bool = True) -> List[Issue]:
        """Get issues from the issue provider between the start date and end date."""
        cached_issues = self._get_cached_issues(start, end)
        if cached_issues:
            return cached_issues.issues

        new_issues = self._fetch_issues(start, end, get_comments)
        cached_issues = IssueCache(start, end, get_comments)
        for issue in new_issues:
            cached_issues.add_issue(issue)
        self._stored_issues.append(cached_issues)
        return new_issues

    def get_issues_by_milestone(self, milestone_name: str) -> Union[List[Issue], None]:
        """Get a list of issues associated with a milestone."""
        for issue_cache in self._stored_issues:
            if issue_cache.milestone == milestone_name:
                return issue_cache.issues

        new_issues = self._fetch_issues_by_milestone(milestone_name)
        new_cache = IssueCache(milestone=milestone_name)
        for issue in new_issues:
            new_cache.add_issue(issue)
        self._stored_issues.append(new_cache)
        return new_issues

    @abstractmethod
    def _fetch_issues(self, start: datetime.datetime, end: datetime.datetime,
                      get_comments: bool) -> List[Issue]:
        """Get issues from the issue provider between the start date and end date."""
        raise NotImplementedError("Not implemented in base class.")

    @abstractmethod
    def _fetch_issues_by_milestone(self, milestone_name: str) -> List[Issue]:
        """Get issues associated with the given milestone from the issue provider."""
        raise NotImplementedError("Not implemented in base class.")

    def _get_cached_issues(self, start: datetime.datetime,
                           end: datetime.datetime) -> Union[IssueCache, None]:
        """Check whether issues with the specified start and end date are already stored."""
        for cache in self._stored_issues:
            if cache.start and cache.end:
                if cache.start == start and cache.end == end:
                    return cache
        else:
            return None


class GitLabIssueServer(IssueServer):
    """An IssueServer with GitLab as the server."""

    def __init__(self, issue_source: dict):
        super().__init__()
        if "token" in issue_source:
            token = issue_source["token"]
        else:
            token = None
        gitlab_server = gitlab_tools.GitlabServer(issue_source["url"], token)
        self.project = gitlab_server.open_gitlab_project(issue_source["project"])

    def _fetch_issues(self, start: datetime.datetime, end: datetime.datetime,
                      get_comments=True) -> List[Issue]:
        """Function to return issues falling withing a certain time window.

        :param start: The start of the time window for included issues
        :param end: The end of the time window for included issues.
        :param get_comments: Whether or not to download issue comments from the server.
          This may take some time if there are a large number of issues so should be disabled
          if the comments are not needed.
        :return: A list of Issue objects.
        """
        request_parameters = {}
        if start is not None:
            request_parameters['created_after'] = start.isoformat()
        if end is not None:
            request_parameters['created_before'] = end.isoformat()

        gitlab_issues = self.project.issues.list(all=True,
                                                 query_parameters=request_parameters)

        return [Issue(gitlab_issue, "gitlab", get_comments) for gitlab_issue in gitlab_issues]

    def _fetch_issues_by_milestone(self, milestone_name: str) -> List[Issue]:
        """Get all gitlab issues associated with a particular milestone.

        :param milestone_name: The name of the milestone to find.
        """
        project_milestones = self.project.milestones.list()

        for milestone in project_milestones:
            if milestone.attributes["title"] == milestone_name:
                milestone_issues = list(milestone.issues())
                return [Issue(issue, "gitlab") for issue in milestone_issues]
        # If the milestone exists but there are no issues associated with it.
        return []


class GitHubIssueServer(IssueServer):
    def __init__(self, issue_server_source: dict):
        super().__init__()
        server = GithubServer(issue_server_source)
        self.repo = server.open_github_repo(issue_server_source["project"])

    def _fetch_issues(self, start: datetime.datetime, end: datetime.datetime,
                      get_comments: bool) -> List[Issue]:
        # TODO: This method does not check issue [opening] end date
        issues = self.repo.get_issues(state="all", since=start)
        return [Issue(issue, "github") for issue in issues if not issue.pull_request]

    def _fetch_issues_by_milestone(self, milestone_name: str) -> List[Issue]:
        milestones = self.repo.get_milestones()
        for milestone in milestones:
            if milestone.title == milestone_name:
                issues = self.repo.get_issues(milestone=milestone, state="all")
                return [Issue(issue, "github") for issue in issues]
        # If milestone not found
        return []


class IssueComment:
    """A comment is a textual field attached to an Issue

    :ivar text: (string) The content of the comment message.
    :ivar created_at: (datetime) The time a comment was made.
    :ivar updated_at: (datetime) The most recent time the content of a comment was updated.
    """
    def __init__(self, comment, source: str):
        self.text = None
        self.created_at = None
        self.updated_at = None
        self.system = None
        self.author = None

        if source == "gitlab":
            self._comment_from_gitlab(comment)
        elif source == "github":
            self._comment_from_github(comment)
        elif source == "test data":
            self._comment_from_test_data(comment)
        else:
            raise TypeError(f"Unknown commit comment source: '{source}'.")

    def _comment_from_gitlab(self, comment: ProjectIssueNote):
        """Populate an instance of a comment from a GitLab note."""
        self.text = clean(comment.attributes["body"])
        self.created_at = string_to_datetime(comment.attributes["created_at"])
        self.updated_at = string_to_datetime(comment.attributes["updated_at"])
        self.system = comment.attributes["system"]
        self.author = comment.attributes["author"]["username"]

    def _comment_from_github(self, comment: github.IssueComment):
        self.text = comment.body
        self.created_at = comment.created_at
        self.updated_at = comment.updated_at
        self.author = comment.user["login"]

    def _comment_from_test_data(self, comment: Tuple[str, datetime.datetime, datetime.datetime, str, str]):
        (text, created_at, updated_at, system, author_name) = comment
        self.text = text
        self.created_at = created_at
        self.updated_at = updated_at
        self.system = system
        self.author = author_name


def get_issue_by_title(issues: List[Issue], title: str) -> Union[Issue, None]:
    """If issue with 'title' exists in 'issues', return the issue, else return None.

    :param issues: A list of Issue objects.
    :param title: An issue title
    :returns: Issue with title == title, else None.
    """
    for issue in issues:
        if issue.title == title:
            return issue
    return None


def new_issue_server(robota_config: dict) -> Union[None, IssueServer]:
    """A factory method for IssueServers."""
    issue_server_source = config_readers.get_data_source_info(robota_config, 'issues')
    if not issue_server_source:
        return None
    server_type = issue_server_source["type"]
    logger.debug(f"Initialising {server_type} issue server.")

    if server_type == 'gitlab':
        return GitLabIssueServer(issue_server_source)
    if server_type == 'github':
        return GitHubIssueServer(issue_server_source)
    else:
        raise TypeError(f"Unknown issue server type {server_type}.")
