"""Property-based tests using Hypothesis.

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
import re
import string

from hypothesis import HealthCheck, Verbosity, given, note, settings
from hypothesis import strategies as st
from hypothesis.database import DirectoryBasedExampleDatabase

from robota_core.commit import Commit
from robota_core.string_processing import (
    append_list_to_dict,
    html_newlines,
    replace_none,
)

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
    database=DirectoryBasedExampleDatabase(".hypothesis/examples"),
)
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "default"))


# A character set that includes newlines alongside printable ASCII.
# Restricting the alphabet (rather than using all Unicode) makes it much more
# likely that Hypothesis generates strings containing '\n' within the available
# example budget.
_printable_with_newline = st.text(
    alphabet='\n ' + string.ascii_letters + string.digits + string.punctuation
)


@given(text=_printable_with_newline)
def test_html_newlines_br_count_equals_newline_group_count(text):
    """html_newlines() replaces each run of one or more consecutive newlines
    with a single '<br>'.  The number of '<br>' tokens in the output must
    therefore equal the number of newline groups (maximal runs of '\\n') in the
    input.
    """
    result = html_newlines(text)
    note(f"input:  {text!r}")
    note(f"output: {result!r}")
    newline_group_count = len(re.findall(r'\n+', text))
    assert result.count('<br>') == newline_group_count


_any_or_none = st.one_of(st.none(), st.integers(), st.text(), st.booleans())


@given(lst=st.lists(_any_or_none, max_size=50))
def test_replace_none_preserves_length(lst):
    """replace_none() must return a list of the same length as its input."""
    result = replace_none(lst)
    note(f"input:  {lst!r}")
    note(f"output: {result!r}")
    assert len(result) == len(lst)


@given(lst=st.lists(_any_or_none, max_size=50))
def test_replace_none_contains_no_nones(lst):
    """replace_none() must return a list that contains no None entries."""
    result = replace_none(lst)
    note(f"input:  {lst!r}")
    note(f"output: {result!r}")
    assert None not in result


@given(lst=st.lists(st.one_of(st.none(), st.integers(), st.booleans()), max_size=50))
def test_replace_none_replacement_count_matches_none_count(lst):
    """Every None in the input must become the replacement value.

    By restricting the input strategy to integers and booleans (no strings),
    the sentinel replacement string cannot already appear in the list, so
    the count of replacement values in the output must equal exactly the
    number of None values in the input.
    """
    sentinel = "REPLACED"
    result = replace_none(lst, replacement=sentinel)
    none_count = sum(1 for x in lst if x is None)
    replaced_count = sum(1 for x in result if x == sentinel)
    note(f"input:         {lst!r}")
    note(f"output:        {result!r}")
    note(f"none_count:    {none_count}")
    note(f"replaced_count: {replaced_count}")
    assert replaced_count == none_count


@given(
    key=st.text(min_size=1, max_size=20),
    new_values=st.lists(st.text(max_size=10), max_size=10),
    existing_values=st.lists(st.text(max_size=10), max_size=10),
    has_existing=st.booleans(),
)
def test_append_list_to_dict_key_present_and_values_preserved(
        key, new_values, existing_values, has_existing):
    """append_list_to_dict() must always result in the key being present.
    All new_values must appear in the final list, and any values already
    stored under the key must be retained.
    """
    d = {}
    if has_existing:
        d[key] = list(existing_values)

    append_list_to_dict(d, key, new_values)

    note(f"key:            {key!r}")
    note(f"new_values:     {new_values!r}")
    note(f"existing_values:{existing_values!r} (present={has_existing})")
    note(f"result:         {d[key]!r}")

    assert key in d
    for item in new_values:
        assert item in d[key]
    if has_existing:
        for item in existing_values:
            assert item in d[key]


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
