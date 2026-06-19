"""Property-based tests using Hypothesis.

These tests exercise pure, self-contained functions in robota_core that do not
require any network access to real GitHub or GitLab repositories.  All five
tests operate entirely on in-process data structures or locally-constructed
objects.

Hypothesis profiles
-------------------
Two profiles are registered here:

* ``default`` – used when running locally; runs up to 100 examples per test.
* ``ci``       – used in CI; limited to 50 examples per test and suppresses the
  ``too_slow`` health-check so that the suite finishes quickly.

The active profile is selected via the ``HYPOTHESIS_PROFILE`` environment
variable (defaulting to ``default``).  The GitHub Actions workflow sets
``HYPOTHESIS_PROFILE=ci`` so CI runs are fast and deterministic.

Logging
-------
``settings(verbosity=Verbosity.verbose)`` causes Hypothesis to print each
generated example to stdout.  The ``note()`` calls inside the tests attach
extra context that appears in the failure report when an example is shrunk.
"""

import os

from hypothesis import HealthCheck, Verbosity, given, note, settings
from hypothesis import strategies as st

from robota_core.commit import Commit
from robota_core.string_processing import (
    html_newlines,
    list_to_html_rows,
    replace_none,
)

# ---------------------------------------------------------------------------
# Hypothesis profile setup
# ---------------------------------------------------------------------------

settings.register_profile(
    "default",
    max_examples=100,
    verbosity=Verbosity.verbose,
)
settings.register_profile(
    "ci",
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow],
    verbosity=Verbosity.verbose,
)
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "default"))


# ---------------------------------------------------------------------------
# Test 1: html_newlines – all newline characters are replaced
# ---------------------------------------------------------------------------

@given(text=st.text())
def test_html_newlines_no_bare_newlines_in_result(text):
    """After calling html_newlines(), the result must not contain bare '\\n'.

    Every newline sequence in the input is converted to '<br>', so the
    output should be free of '\\n' characters regardless of what the
    input looks like.
    """
    result = html_newlines(text)
    note(f"input:  {text!r}")
    note(f"output: {result!r}")
    assert "\n" not in result


# ---------------------------------------------------------------------------
# Test 2: replace_none – length is preserved
# ---------------------------------------------------------------------------

_any_or_none = st.one_of(st.none(), st.integers(), st.text(), st.booleans())


@given(lst=st.lists(_any_or_none, max_size=50))
def test_replace_none_preserves_length(lst):
    """replace_none() must return a list of the same length as its input."""
    result = replace_none(lst)
    note(f"input:  {lst!r}")
    note(f"output: {result!r}")
    assert len(result) == len(lst)


# ---------------------------------------------------------------------------
# Test 3: replace_none – output contains no None values
# ---------------------------------------------------------------------------

@given(lst=st.lists(_any_or_none, max_size=50))
def test_replace_none_contains_no_nones(lst):
    """replace_none() must return a list that contains no None entries."""
    result = replace_none(lst)
    note(f"input:  {lst!r}")
    note(f"output: {result!r}")
    assert None not in result


# ---------------------------------------------------------------------------
# Test 4: list_to_html_rows – splitting on '<br>' recovers the original list
# ---------------------------------------------------------------------------

_safe_string = st.text(
    alphabet=st.characters(exclude_characters=["<", ">", "&"]),
    max_size=80,
)


@given(items=st.lists(_safe_string, max_size=20))
def test_list_to_html_rows_split_roundtrip(items):
    """Splitting the output of list_to_html_rows() on '<br>' should give back
    the original list of strings, provided those strings do not themselves
    contain '<br>'.
    """
    joined = list_to_html_rows(items)
    note(f"items:  {items!r}")
    note(f"joined: {joined!r}")
    if items:
        assert joined.split("<br>") == items
    else:
        assert joined == ""


# ---------------------------------------------------------------------------
# Test 5: Commit.merge_commit – property derived from parent count
# ---------------------------------------------------------------------------

_commit_id = st.text(
    alphabet="0123456789abcdef",
    min_size=1,
    max_size=40,
    # Deliberately allow variable-length hex strings: the merge-commit
    # property depends only on parent count, not on SHA format.
)


@given(
    commit_id=_commit_id,
    extra_parent_ids=st.lists(_commit_id, min_size=0, max_size=4),
    has_two_parents=st.booleans(),
    extra_id=_commit_id,
)
def test_commit_from_dict_merge_detection(commit_id, extra_parent_ids, has_two_parents, extra_id):
    """A Commit built from a dict with more than one parent id must be flagged
    as a merge commit; one with zero or one parent must not be.

    No network access is required: the 'dict' source path constructs the
    Commit entirely from the supplied dictionary.
    """
    if has_two_parents:
        # Guarantee at least 2 *distinct* parents by using a separate extra_id
        # when the list is otherwise empty.
        parent_ids = [commit_id, *extra_parent_ids]
        if len(parent_ids) < 2:
            parent_ids.append(extra_id)
    else:
        parent_ids = extra_parent_ids[:1]  # 0 or 1 parent

    commit_data = {"id": commit_id, "parents": parent_ids}
    commit = Commit(commit_data, "dict")

    note(f"commit_id:  {commit_id!r}")
    note(f"parent_ids: {parent_ids!r}")
    note(f"merge_commit: {commit.merge_commit}")

    if len(parent_ids) > 1:
        assert commit.merge_commit is True
    else:
        assert commit.merge_commit is False
