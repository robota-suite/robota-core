# Unit and simple integration tests for functionality concerning issue handling
from datetime import datetime, timedelta
from unittest import TestCase

from robota_core.issue import Issue, IssueComment


class TestIssueHandling(TestCase):
    @staticmethod
    def test_fetch_earliest_matching_comment():
        text_to_match = "changed due date to"
        first_date = datetime(2020, 1, 1, hour=12)
        one_day = timedelta(days=1)
        two_days = timedelta(days=2)
        update_date = datetime(2020, 5, 5)
        test_issue = Issue((1, 'GUI bug'), "test data")
        author1 = "jemima.puddleduck"
        author2 = "jfisher572"
        # A list of comments in non-chronological order
        test_issue.comments = [
            IssueComment(("removed milestone", first_date + one_day, update_date, True, author1), "test data"),
            IssueComment((text_to_match, first_date + two_days, update_date, True, author1), "test data"),
            IssueComment(("Tests completed for this issue", first_date - one_day, update_date, False, author2), "test data"),
            IssueComment((text_to_match, first_date, update_date, True, author2), "test data"),
            IssueComment(("changed time estimate to", first_date - two_days, update_date, True, author2), "test data")
        ]

        assert test_issue.get_comment_timestamp(text_to_match, earliest=True) == first_date
        assert test_issue.get_comment_timestamp(text_to_match, earliest=False) == first_date + two_days

    def test_identify_sub_team_membership_in_issue_comments(self):
        key_phrase = 'Sub team member:'
        # Set up an issue with comments covering all the key cases.
        # We don't care about the order of these comments or when they were made, so use a dummy date
        test_issue = Issue((1, 'GUI bug'), "test data")
        dummy_date = None
        dummy_author = "anne.author"
        test_issue.comments = [
            # An irrelevant comment
            IssueComment(("removed milestone", dummy_date, dummy_date, True, dummy_author), "test data"),
            # An irrevelvant comment containing a username
            IssueComment(("Code review by: @a12345bc", dummy_date, dummy_date, True, dummy_author), "test data"),

            # A sub-team assignment of the form: key_phrase @username
            IssueComment((key_phrase + " @d23456ef", dummy_date, dummy_date, True, dummy_author), "test data"),

            # A sub-team assignment of the form: key_phrase https://gitlab.cs.man.ac.uk/username
            IssueComment((key_phrase + " https://gitlab.cs.man.ac.uk/g34567hi", dummy_date, dummy_date, True, dummy_author), "test data"),
            # A sub-team assignment of the form: key_phrase https://gitlab.cs.man.ac.uk/user.name
            IssueComment((key_phrase + " https://gitlab.cs.man.ac.uk/some.one", dummy_date, dummy_date, True, dummy_author), "test data"),
            # A sub-team assignment of the form: key_phrase https://gitlab.cs.man.ac.uk/user-name
            IssueComment((key_phrase + " https://gitlab.cs.man.ac.uk/person-two", dummy_date, dummy_date, True, dummy_author), "test data"),

            # A sub-team assignment of the form: key_phrase [https://gitlab.cs.man.ac.uk/username]
            IssueComment((key_phrase + " [https://gitlab.cs.man.ac.uk/j45678kl]", dummy_date, None, True, dummy_author), "test data"),
            # A sub-team assignment of the form: key_phrase <https://gitlab.cs.man.ac.uk/user.name>
            IssueComment((key_phrase + " <https://gitlab.cs.man.ac.uk/m56789no>", dummy_date, None, True, dummy_author), "test data")
        ]

        actualTeamMembers = test_issue.get_recorded_team_member(key_phrase)
        expectedTeamMembers = ["d23456ef", "g34567hi", "some.one", "person-two", "j45678kl", "m56789no"]
        self.assertCountEqual(actualTeamMembers, expectedTeamMembers)
