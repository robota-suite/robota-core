import datetime
from typing import List, Union

import gitlab
import github.PullRequest
import github.PullRequestComment
import github.IssueComment

from robota_core.string_processing import markdownify, clean, string_to_datetime, get_link


class MergeRequest:
    """A Merge Request"""
    def __init__(self, merge_request, source: str):
        self.number: Union[int, None] = None
        self.source_branch = None
        self.target_branch = None
        self.author = None
        self.url: str = ""
        self.comments = None
        self.state = None

        if source == "gitlab":
            self._merge_request_from_gitlab(merge_request)
        elif source == "github":
            self._merge_request_from_github(merge_request)
        else:
            raise TypeError("Merge request type not recognised.")

        self.link = get_link(self.url, self.number)

    def _merge_request_from_github(self, merge_request: github.PullRequest.PullRequest):
        self.number = merge_request.number
        self.source_branch = merge_request.head.ref
        self.target_branch = merge_request.base.ref
        self.author = merge_request.user.name
        self.url = merge_request.html_url
        comments = list(merge_request.get_issue_comments())
        comments.extend(merge_request.get_comments())
        self.comments = [MergeRequestComment(comment, "github") for comment in comments]
        self.state = merge_request.state

    def _merge_request_from_gitlab(self, gl_merge_request: gitlab.v4.objects.ProjectMergeRequest):
        """Convert a GitLab merge request into a RoboTA merge request"""
        self.number = gl_merge_request.attributes['iid']
        self.source_branch = gl_merge_request.attributes["source_branch"]
        self.target_branch = gl_merge_request.attributes["target_branch"]
        self.author = gl_merge_request.attributes['author']
        self.url = gl_merge_request.attributes['web_url']
        self.comments = [MergeRequestComment(note, "gitlab") for
                         note in gl_merge_request.notes.list()]
        self.state = gl_merge_request.attributes['state']


class MergeRequestCache:
    """A cache of MergeRequest objects from a specific date range."""
    def __init__(self, start: datetime.datetime, end: datetime.datetime,
                 merge_requests: List[MergeRequest]):
        self.start = start
        self.end = end
        self.merge_requests = merge_requests

    def __iter__(self):
        yield from self.merge_requests

    def add_merge_request(self, merge_request: MergeRequest):
        """Add a MergeRequest to a MergeRequestCache."""
        self.merge_requests.append(merge_request)


class MergeRequestComment:
    """Comments on a merge request"""
    def __init__(self, comment, source: str):
        self.body = None
        self.author = None
        self.created_at = None

        if source == "gitlab":
            self._comment_from_gitlab_merge_request(comment)
        elif source == "github":
            self._comment_from_github_merge_request(comment)
        else:
            raise TypeError("Merge request type not recognised.")

    def _comment_from_github_merge_request(self, gh_mr_note: Union[
          github.PullRequestComment.PullRequestComment, github.IssueComment.IssueComment]):
        self.body = markdownify(clean(gh_mr_note.body))
        self.author = gh_mr_note.user.name
        self.created_at = gh_mr_note.created_at

    def _comment_from_gitlab_merge_request(self,
                                           gl_mr_note: gitlab.v4.objects.ProjectMergeRequestNote):
        self.body = markdownify(clean(gl_mr_note.attributes['body']))
        self.author = gl_mr_note.attributes['author']
        self.created_at = string_to_datetime(gl_mr_note.attributes['created_at'])
