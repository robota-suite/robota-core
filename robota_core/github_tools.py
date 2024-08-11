from loguru import logger

import github
import github.Repository

from robota_core import RemoteProviderError


class GithubServer:
    """A connection to GitHub. Contains methods for interfacing with the API."""
    def __init__(self, setup: dict):
        """ Initialise the connection to the server, getting credentials from the credentials file.

        :param setup: dictionary containing GitHub url and authentication token.
        """
        self.url = setup["url"]
        self.server = self._open_gitlab_connection(setup)

    @staticmethod
    def _open_gitlab_connection(setup: dict):
        """Open a connection to the GitLab server using authentication token."""
        token = None
        if "token" in setup:
            token = setup["token"]
        else:
            logger.warning("No auth token provided for Github. Beware that API limits are very "
                            "low for unauthenticated users.")
        return github.Github(token)

    def open_github_repo(self, project_path: str) -> github.Repository.Repository:
        """Open a GitLab repo.

        :param project_path: The path of the project to open. Includes namespace.
        :return: A GitLab project object.
        """
        try:
            repo = self.server.get_repo(project_path)
        except github.UnknownObjectException:
            raise RemoteProviderError(f"Unable to find project: {project_path}. "
                                      f"It either does not exist or the current user does not have "
                                      f"access to this project.")

        logger.info(f"Connected to project {repo.name}")
        return repo
