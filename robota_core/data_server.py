from datetime import datetime
from typing import Union, List

from robota_core.remote_provider import RemoteProvider, new_remote_provider
from robota_core.repository import new_repository, Repository
from robota_core.issue import new_issue_server, IssueServer
from robota_core.ci import new_ci_server, CIServer


class DataServer:
    """A container for data sources."""

    def __init__(self, robota_config: dict, start: datetime, end: datetime):
        # Set up connection to student repo
        self.repository: Union[Repository, None] = new_repository(robota_config)
        self.remote_provider: Union[RemoteProvider, None] = new_remote_provider(robota_config)
        self.issue_server: Union[IssueServer, None] = new_issue_server(robota_config)
        self.ci_server: Union[CIServer, None] = new_ci_server(robota_config)

        self.start = start
        self.end = end
        self._valid_sources: Union[None, List[str]] = None

    def get_valid_sources(self) -> List[str]:
        """Check whether each of the data sources has been successfully initialised."""
        if self._valid_sources is not None:
            return self._valid_sources

        # Populate the valid sources list
        self._valid_sources = []
        if self.repository:
            self._valid_sources.append("repository")
        if self.remote_provider:
            self._valid_sources.append("remote_provider")
        if self.issue_server:
            self._valid_sources.append("issues")
        if self.ci_server:
            self._valid_sources.append("ci")
        return self._valid_sources
