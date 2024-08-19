import pytest
from robota_core.repository import GitlabRepository, GithubRepository

class TestGithubUrls:
    repo = "https://github.com/robota-suite/robota-core"
    project = "robota-suite/robota-core"

    def test_branch_url(self):
        server = GithubRepository({
            "url": self.repo,
            "project": self.project
        })

        develop_branch = server.get_branch('develop')

        assert develop_branch.url == "https://github.com/robota-suite/robota-core/tree/develop"
