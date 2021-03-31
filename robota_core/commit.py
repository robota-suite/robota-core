"""Objects and for describing and processing Git commits."""

import datetime
import copy
from typing import List, Union, TYPE_CHECKING

import dateparser
import dateutil.parser
import gitlab.v4.objects
import github.Tag
import github.Commit
import github.CommitComment
import github.GithubObject
import git

from robota_core.string_processing import clean, get_link

if TYPE_CHECKING:
    from robota_core.repository import Event


class Commit:
    """An abstract object representing a git commit.

    :ivar created_at: (datetime) Commit creation time.
    :ivar id: Commit id.
    :ivar parent_ids: (List[string]) The ids of one or more commit parents.
    :ivar raw_message: (str) The original commit message
    :ivar message: (str) The commit message cleaned for HTML display.
    :ivar merge_commit: (bool) Whether this commit is a merge commit.
    """
    def __init__(self, commit, commit_source: str, project_url: str = None):
        self.created_at = None
        self.id = None
        self.author_name = None    # Used only for progress report
        self.short_id = None
        self.parent_ids = None
        self.raw_message = ""
        self.email = None
        self.comments: List["CommitComment"] = []
        self.url = None
        self.link = None
        self.network_url = None
        self.network_link = None

        if commit_source == "gitlab":
            self._commit_from_gitlab(commit, project_url)
        elif commit_source == "github":
            self._commit_from_github(commit)
        elif commit_source == "local":
            self.commit_from_local(commit)
        elif commit_source == "dict":
            self._commit_from_dict(commit)
        else:
            raise TypeError(f"Unknown commit type '{commit_source}'")

        self.message = clean(self.raw_message)
        self.merge_commit = self._is_merge_commit()

    def __hash__(self):
        return hash(self.id)

    def __repr__(self):
        return f"{self.short_id}"

    def get_comments(self) -> List[str]:
        """Return the text of all comments to this commit."""
        return [comment.text for comment in self.comments]

    def __eq__(self, other_commit: Union[None, "Commit"]):
        if other_commit is None:
            return False
        elif self.id == other_commit.id:
            return True
        else:
            return False

    def _commit_from_github(self, github_commit: github.Commit.Commit):
        commit = github_commit.commit

        created_at = dateutil.parser.parse(commit.last_modified)
        self.created_at = created_at.replace(tzinfo=None)
        self.id = commit.sha
        self.author_name = commit.author.name
        self.short_id = self.id[:10]
        self.parent_ids = [parent.sha for parent in commit.parents]
        self.raw_message = commit.message
        self.email = commit.author.email
        comments = github_commit.get_comments()
        self.comments = [CommitComment(comment, "gitlab") for comment in comments]
        self.url = commit.html_url
        self.link = get_link(self.url, self.short_id)

    def _commit_from_gitlab(self, gitlab_commit: gitlab.v4.objects.ProjectCommit, project_url: str):
        """Convert a Gitlab commit to RoboTA Commit."""
        created_at = dateparser.parse(gitlab_commit.attributes["created_at"])
        self.created_at = created_at.replace(tzinfo=None)
        self.id = gitlab_commit.attributes["id"]
        self.author_name = gitlab_commit.attributes["author_name"]
        self.short_id = gitlab_commit.attributes["short_id"]
        self.parent_ids = gitlab_commit.attributes["parent_ids"]
        self.raw_message = gitlab_commit.attributes["message"]
        self.email = gitlab_commit.attributes['author_email'].lower()
        comments = gitlab_commit.comments.list(all=True)
        self.comments = [CommitComment(comment, "gitlab") for comment in comments]
        self.url = f'{project_url}/commit/{self.id}'
        self.link = get_link(self.url, self.short_id)
        self.network_url = f'{project_url}/network/master?utf8=✓&extended_sha1={self.id}'
        self.network_link = get_link(self.network_url, self.short_id)

    def commit_from_local(self, commit: git.Commit):
        self.created_at = commit.authored_datetime
        self.id = commit.hexsha
        self.author_name = commit.author.name
        self.short_id = self.id[:10]
        self.parent_ids = [parent.hexsha for parent in commit.parents]
        self.raw_message = commit.message
        self.email = commit.author.email

    def _commit_from_dict(self, commit: dict):
        """Used for testing, create a commit with just the ID and ID of parents."""
        self.id = commit["id"]
        if "parents" in commit:
            self.parent_ids = commit["parents"]
        else:
            self.parent_ids = []

    def _is_merge_commit(self) -> bool:
        """Is this a merge commit? Only a merge commit can have more than one parent.

        :return: Whether this is a merge commit
        """
        if len(self.parent_ids) > 1:
            return True
        else:
            return False


class CommitComment:
    """A comment made on a commit."""
    def __init__(self, comment_data, source: str):
        self.text = None
        self.author = None

        if source == "gitlab":
            self._commit_comment_from_gitlab(comment_data)
        elif source == "github":
            self._commit_comment_from_github(comment_data)
        else:
            raise TypeError("Unknown commit comment data type.")

    def _commit_comment_from_gitlab(self, comment_data: gitlab.v4.objects.ProjectCommitComment):
        self.text = clean(comment_data.attributes["note"])
        self.author = comment_data.attributes['author']

    def _commit_comment_from_github(self, comment_data: github.CommitComment.CommitComment):
        self.text = comment_data.body
        self.author = comment_data.user.name


class Tag:
    """A tag is a named pointer to a git commit.

    :ivar name: The name of the tag.
    :ivar commit_id: The id of the commit that the tag points to.
    """
    def __init__(self, tag_data, source: str):
        self.name = ""
        self.commit_id = ""

        if source == "gitlab":
            self.tag_from_gitlab(tag_data)
        elif source == "github":
            self.tag_from_github(tag_data)
        elif source == "local":
            self.tag_from_local(tag_data)
        elif source == "dict":
            self.tag_from_dict(tag_data)
        else:
            raise TypeError(f"Cannot create tag, unknown tag data type: {source}")

    def tag_from_gitlab(self, tag_data: gitlab.v4.objects.ProjectTag):
        self.name = tag_data.attributes["name"]
        self.commit_id = tag_data.attributes["commit"]["id"]

    def tag_from_dict(self, tag_data: dict):
        self.name = tag_data["name"]
        self.commit_id = tag_data["commit_id"]

    def tag_from_local(self, tag_data: git.Tag):
        self.name = tag_data.name
        self.commit_id = tag_data.commit.hexsha

    def tag_from_github(self, tag_data: github.Tag.Tag):
        self.name = tag_data.name
        self.commit_id = tag_data.commit.sha


class CommitCache:
    """A cache of Commit objects from a specific date range and branch."""
    def __init__(self, start: datetime.datetime, end: datetime.datetime, branch: str,
                 commits: List[Commit]):
        self.start = start
        self.end = end
        self.branch = branch
        self.commits = tuple(commits)

    def __iter__(self):
        yield from self.commits


def get_merge_commit(feature_tip: Commit, master_commits: List[Commit]) -> Union[Commit, None]:
    """Get merge commit ID for the branch "branch_title".
    Given the id of the commit at the tip of a feature branch, find where it merges into the
    master branch by going through the commits ids on the master branch and looking at their
    parents.

    :param feature_tip: The Commit at the tip of the feature branch.
    :param master_commits: Commits of master branch, ordered by date, most recent first.
    :return merge_commit: The id of the merge commit if branch was merged else returns None.
    """
    if not master_commits:
        return None

    assert isinstance(feature_tip, Commit)

    # Find where the branch tip is in the list of master Commits
    master_commit_index = None
    for index, commit in enumerate(master_commits):
        if commit == feature_tip:
            master_commit_index = index
            break
    if master_commit_index is None:
        # Branch was not merged
        return None

    # Search for merge commits in the more recent commits.
    for commit in reversed(master_commits[:master_commit_index]):
        if len(commit.parent_ids) > 1 and feature_tip.id == commit.parent_ids[1]:
            # Non-FF merge
            return commit
    # FF merge
    return feature_tip


def get_tags_at_date(date: datetime.datetime, tags: List[Tag],
                     events: List["Event"]) -> List[Tag]:
    tags = copy.deepcopy(tags)

    for event in events:
        if event.date > date:
            # Add tags that have been deleted since date.
            if event.type == "deleted":
                if event.ref_type == "tag":
                    tag_data = {"name": event.ref_name,
                                "commit_id": event.commit_id}
                    tags.append(Tag(tag_data, "dict"))

            # Remove tags that have been added since date.
            elif event.type == "pushed to" or event.type == "pushed new":
                if event.ref_type == "tag":
                    tag_name = event.ref_name
                    tag_commit = event.commit_id
                    pointer = 0
                    while pointer < len(tags):
                        if tags[pointer].commit_id == tag_commit and tags[pointer].name == tag_name:
                            del (tags[pointer])
                        else:
                            pointer += 1
    return tags
