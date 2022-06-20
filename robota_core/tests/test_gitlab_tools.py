""""Tests for gitlab_tools.py"""
from datetime import datetime, timedelta

import gitlab
import pytest

from robota_core.gitlab_tools import GitlabServer
from robota_core.issue import Issue, IssueComment
from robota_core.repository import Event
from robota_core import commit


class TestOpenGitlab:
    """Test the open gitlab function"""
    bad_url = "http://www.google.com/"
    bad_token = "aaa"

    def test_bad_url(self):
        """A bad URL should raise a different error."""
        with pytest.raises(gitlab.exceptions.GitlabGetError):
            _ = GitlabServer(self.bad_url, self.bad_token)


class IssueTests:
    @staticmethod
    def test_fetch_earliest_matching_comment():
        text_to_match = "changed due date to"
        first_date = datetime(1, 1, 2020, hour=12)
        one_day = timedelta(days=1)
        two_days = timedelta(days=2)
        update_date = datetime(5, 5, 2020)
        test_issue = Issue((1, 'GUI bug'), "test data")
        # A list of comments in non-chronological order
        test_issue.comments = [
            IssueComment(("removed milestone", first_date + one_day, update_date, True), "test data"),
            IssueComment((text_to_match, first_date + two_days, update_date, True), "test data"),
            IssueComment(("Tests completed for this issue", first_date - one_day, update_date, False), "test data"),
            IssueComment((text_to_match, first_date, update_date, True), "test data"),
            IssueComment(("changed time estimate to", first_date - two_days, update_date, True), "test data")
        ]

        assert test_issue.get_comment_timestamp(text_to_match, earliest=True) == first_date
        assert test_issue.get_comment_timestamp(text_to_match, earliest=False) == first_date + two_days


class TestGetTags:
    @staticmethod
    def test_added_tag_after_deadline():
        # Test for the case that a branch has been added since deadline and so should be removed.
        tags = [commit.Tag({"name": "master", "commit_id": "111"}, "dict"),
                commit.Tag({"name": "develop", "commit_id": "222"}, "dict"),
                commit.Tag({"name": "feature", "commit_id": "333"}, "dict")]

        events = [Event({"date": "2020-01-02T00:00:00.000Z", "type": "pushed new",
                         "push_data": {"ref_type": "tag", "ref_name": "feature",
                                       "commit_id": "333", "commit_count": "1"}})]

        tags = commit.get_tags_at_date(datetime(2020, 1, 1), tags, events)
        assert isinstance(tags, list)
        assert len(tags) == 2
        assert tags[0].name == "master"
        assert tags[1].name == "develop"

    @staticmethod
    def test_deleted_tag_after_deadline():
        # Test for the case that a branch has been deleted since deadline and so should be added.
        tags = [commit.Tag({"name": "master", "commit_id": "111"}, "dict"),
                commit.Tag({"name": "develop", "commit_id": "222"}, "dict")]

        events = [Event({"date": "2020-01-02T00:00:00.000Z", "type": "deleted",
                         "push_data": {"ref_type": "tag", "ref_name": "feature",
                                       "commit_id": "333", "commit_count": "1"}})]

        tags = commit.get_tags_at_date(datetime(2020, 1, 1), tags, events)
        assert isinstance(tags, list)
        assert len(tags) == 3
        assert tags[0].name == "master"
        assert tags[1].name == "develop"
        assert tags[2].name == "feature"

    @staticmethod
    def test_tag_changed_after_deadline():
        # Test for the case that a branch has been added and deleted since deadline
        # and so should not be added.

        tags = [commit.Tag({"name": "master", "commit_id": "111"}, "dict"),
                commit.Tag({"name": "develop", "commit_id": "222"}, "dict")]

        # Events come from gitlab most recent first.
        events = [Event({"date": "2020-01-02T00:01:00.000Z", "type": "deleted",
                         "push_data": {"ref_type": "tag", "ref_name": "feature",
                                       "commit_id": "333", "commit_count": "1"}}),
                  Event({"date": "2020-01-02T00:00:00.000Z", "type": "pushed new",
                         "push_data": {"ref_type": "tag", "ref_name": "feature",
                                       "commit_id": "333", "commit_count": "1"}})
                  ]

        tags = commit.get_tags_at_date(datetime(2020, 1, 1), tags, events)
        assert isinstance(tags, list)
        assert len(tags) == 2
        assert tags[0].name == "master"
        assert tags[1].name == "develop"
