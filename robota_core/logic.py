import datetime
from typing import List, Union

from robota_core.commit import Commit


def is_date_before_other_dates(query_date: datetime.datetime, deadline: datetime.datetime,
                               key_date: datetime.datetime) -> bool:
    """Determine whether an action was before the deadline and another key date.

    :param query_date: The date of the action in question, e.g. when was an issue assigned, time
      estimate set, or due date set.
    :param deadline: The deadline of the action
    :param key_date: The query date should be before this significant date, as well as the
      deadline e.g. branch creation date
    :return: True if issue query_date was before deadline and key_date else False.
    """
    if query_date is not None and key_date is not None:
        assert key_date is not query_date

    if not query_date:
        return False

    if query_date < deadline:
        if not key_date:
            return True
        elif query_date < key_date:
            return True
        else:
            return False
    else:
        return False


def get_first_feature_commit(base_commits: List[Commit],
                             feature_commits: List[Commit]) -> Union[Commit, None]:
    """Get the first commit on a feature branch. Determine first commit by looking for
    branching points, described by the parent commits.
    All parameters are lists of commit IDs ordered from newest to oldest

    :param base_commits: commits from base branch (usually master)
    :param feature_commits: commits from feature branch
    :return first_feature_commit: commit ID of first commit on feature
    """

    # No feature branch commits in specified time range
    if not feature_commits:
        return None

    # To be certain that we have the first commit on feature,
    # there must be a commit common to both lists.
    if feature_commits[-1] != base_commits[-1]:
        raise AssertionError('The oldest commit in each list must be common to both branches.')

    # First check for unmerged feature branch
    # If last feature commit is not in base commits then the feature branch is unmerged
    if feature_commits[0] not in base_commits:
        # Now loop through commits and look at their parents.
        # The parent that is in base is the branching point
        for commit in feature_commits:
            if Commit({"id": commit.parent_ids[0]}, "dict") in base_commits:
                # If a parent is found in base then the commit is the first on the feature branch.
                return commit
        raise AssertionError("Feature branch not connected to master branch.")

    # Feature commit is in both feature and base, so feature parent must be
    # parent to a base commit too. Test for merged feature by looking for merge commit:
    for feature_commit in feature_commits:
        if find_feature_parent(feature_commit, base_commits):
            return feature_commit

    # All feature commits have been tested and neither an unmerged feature
    # branch, nor a merged feature with merge commit were found.
    # This is a FAST-FORWARD MERGE, so return the second commit on the feature branch
    # (the two lists of feature branch commits contains one extra,
    # earlier commit each so that we can always find a common commit).
    return feature_commits[-2]


def find_feature_parent(feature_commit: Commit, base_commits: List[Commit]) -> bool:
    """Determine whether the provided feature commit has a commit in the base branch with a
    common parent.

    :param feature_commit: The feature commit being checked.
    :param base_commits: A list of the base commits, most recent first.
    :returns: True if feature_commit has a common parent with a commit in the
      base branch else False.
    """
    base_commit = base_commits[0]
    while True:
        try:
            feature_parent = feature_commit.parent_ids[0]
        except IndexError:
            feature_parent = None

        if feature_parent in base_commit.parent_ids and base_commit != feature_commit:
            return True

        # The first parent is always the branch being merged into - the base branch
        try:
            base_commit = find_commit_in_list(base_commit.parent_ids[0], base_commits)
        except IndexError:
            base_commit = None

        if not base_commit:
            # If we have gone through all of the base commits and not found feature_parent then
            # this feature commit is not the first in the feature branch
            return False


def find_commit_in_list(commit_id: str, commits: List[Commit]) -> Union[None, Commit]:
    """Find a Commit in a list of Commits by its ID.

    :param commit_id: The id of the commit to find.
    :param commits: The list of Commits to search.
    :return: Commit if found, else None.
    """
    for commit in commits:
        if commit.id == commit_id:
            return commit
    return None


def fixup_first_feature_commit(feature_branch_commits: List[Commit],
                               initial_guess_of_first_commit: Commit, merge_commits: List[Commit]):
    """Fix-up function to look for merge commits on master branch before the tip of the feature
    branch. Any commits up to and including a merge commit in the history of a feature branch
    cannot be the first commit on the feature branch.

    :param feature_branch_commits:
    :return:
    """
    # next_commit means next chronologically, rather than next in the list of commits,
    # which is ordered newest to oldest.
    branch_tip = feature_branch_commits[0]
    next_commit = None
    for commit in feature_branch_commits:
        if commit in merge_commits and commit is not branch_tip:
            if next_commit:
                return next_commit
            else:
                return commit
        next_commit = commit
    else:
        return initial_guess_of_first_commit


def date_is_before(date1: datetime.datetime, date2: datetime.datetime) -> bool:
    """If date1 and date2 are provided and date1 is before date2 return True, else return False."""
    if date1 and date2 and date1 < date2:
        return True
    else:
        return False


def logical_and_lists(list1: List[bool], list2: List[bool]) -> List[bool]:
    """For two lists of booleans of length N, return a list of length N
    where output[i] is True if list1[i] is True and list2[i] is True,
    else output[i] is False.
    """
    assert len(list1) == len(list2)

    return [a and b for a, b in zip(list1, list2)]


def are_list_items_in_other_list(reference_list: List, query_list: List) -> List[bool]:
    """Check whether items in query_list exist in correct_list.

    :param reference_list: The reference list of items
    :param query_list: The items to check - does this list contain items in reference_list?
    :return items_present: Whether items in the correct list are in query_list (bool)

    >>> are_list_items_in_other_list([1, 2, 3], [3, 1, 1])
    [True, False, True]
    """
    items_present = [True if item in query_list else False for item in reference_list]

    return items_present


def are_lists_equal(list_1: list, list_2: list) -> List[bool]:
    """Elementwise comparison of lists. Return list of booleans, one for each element in the
    input lists, True if element N in list 1 is equal to element N in list 2, else False."""
    return [i == j for i, j in zip(list_1, list_2)]


def fraction_of_lists_equal(list_1: list, list_2: list) -> float:
    """Returns the fraction of list elements are equal when compared elementwise."""
    boolean_equals = are_lists_equal(list_1, list_2)
    return boolean_equals.count(True) / len(boolean_equals)


def get_value_from_list_of_dicts(list_of_dicts: List[dict], search_key: str, search_value: int,
                                 return_key: str):
    """Given a list of dictionaries, identify the required dictionary which contains the
    *search_key*: *search_value* pair. Return the value in that dictionary associated
    with *return_key*."""
    assert(search_key != return_key)
    for d in list_of_dicts:
        for k in d:
            if k == search_key and d[k] == search_value:
                return d[return_key]
