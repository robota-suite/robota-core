import pytest

from robota_core.commit_visualisation import commit_visualisation


class TestMain:
    def test_no_branch_no_refs(self):
        all_commits = ["a", "b", "c", "d", "e", "f"]
        commit_parents = [["x"], ["a"], ["b"], ["c"], ["d"], ["e"]]
        refs = {}
        commit_visualisation.process_commits(all_commits, commit_parents, refs)
        try:
            commit_visualisation.render()
        except FileNotFoundError:
            pytest.skip("Graphvis executable not found")

    def test_no_branch(self):
        all_commits = ["a", "b", "c", "d", "e", "f"]
        commit_parents = [["x"], ["a"], ["b"], ["c"], ["d"], ["e"]]
        refs = {"master": "f"}

        commit_visualisation.process_commits(all_commits, commit_parents, refs)
        try:
            commit_visualisation.render()
        except FileNotFoundError:
            pytest.skip("Graphvis executable not found")

    def test_one_branch(self):
        all_commits = ["a", "b", "c", "d", "e", "f"]
        commit_parents = [["x"], ["a"], ["b"], ["c"], ["c", "d"], ["e"]]
        refs = {"master": "f", "feature": "d"}

        commit_visualisation.process_commits(all_commits, commit_parents, refs)
        try:
            commit_visualisation.render()
        except FileNotFoundError:
            pytest.skip("Graphvis executable not found")


class TestGetCommitParents:
    def test_no_branch(self):
        all_commits = ["a", "b", "c", "d", "e", "f"]
        commit_parents = [["x"], ["a"], ["b"], ["c"], ["d"], ["e"]]

        merge_commit_parents = commit_visualisation.identify_merge_commit_parents(commit_parents)
        assert merge_commit_parents == []

    def test_one_branch(self):
        all_commits = ["a", "b", "c", "d", "e", "f"]
        commit_parents = [["x"], ["a"], ["b"], ["c"], ["c", "d"], ["e"]]

        merge_commit_parents = commit_visualisation.identify_merge_commit_parents(commit_parents)
        assert merge_commit_parents == [["c", "d"]]