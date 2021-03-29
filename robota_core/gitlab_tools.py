"""General methods for interfacing with GitLab via the python-Gitlab library."""
import sys

from loguru import logger
import urllib.request
from typing import List

import gitlab.v4.objects


class GitlabGroup:
    """ A group is distinct from a project, a group may contain many projects.
    Projects contained in a group inherit the members of the containing project.
    """
    def __init__(self, gitlab_connection: gitlab.Gitlab, group_name: str):
        self.group_name = group_name
        self.group = gitlab_connection.groups.get(group_name)

    def get_group_members(self) -> List[str]:
        """ Get a list of members in a group.

        :return member_list: Names of members of group.
        """
        member_list = []
        for member in self.group.members.list():
            member_list.append(member.attributes['name'])

        return member_list


class GitlabServer:
    """A connection to the Gitlab server. Contains methods for interfacing with the API. This is
    held distinct from the Repository object because it can also be used to interface with
    an Issue server."""
    def __init__(self, url: str, token: str):
        """ Initialise the connection to the server, getting credentials from the credentials file.

        :param url: url of GitLab server
        :param token: Authentication token for gitlab server.
        """
        self.url = url
        self.token = token

        self.gitlab_connection: gitlab.Gitlab = self._open_gitlab_connection()

    def _open_gitlab_connection(self) -> gitlab.Gitlab:
        """Open a connection to the GitLab server using authentication token."""
        if not self.token:
            logger.error("Must provide an authentication token in robota config to use the "
                         "gitlab API.")
            raise KeyError()
        server = gitlab.Gitlab(self.url, private_token=self.token)
        try:
            server.auth()
        except gitlab.exceptions.GitlabAuthenticationError:
            logger.error("Incorrect authentication token provided. Unable to connect to GitLab.")
            # Exit to prevent really long gitlab stack trace.
            sys.exit(1)
        except gitlab.exceptions.GitlabHttpError:
            logger.error(f"Unable to find gitlab server '{self.url}.")
            sys.exit(1)

        logger.info(f"Logged in to gitlab: '{server.url}' as {server.user.attributes['name']}")

        return server

    def open_gitlab_project(self, project_path: str) -> gitlab.v4.objects.Project:
        """Open a GitLab project.

        :param project_path: The path of the project to open. Includes namespace.
        :return: A GitLab project object.
        """
        if "/" not in project_path:
            raise gitlab.exceptions.GitlabGetError("Must provide namespace "
                                                   "when opening gitlab project.")
        try:
            url_encoded_path = urllib.request.pathname2url(project_path)
            project = self.gitlab_connection.projects.get(url_encoded_path)
        except gitlab.exceptions.GitlabGetError as error_type:
            logger.error(f"Unable to find project: {project_path}. It either does not exist or "
                         f"the current user {self.gitlab_connection.user.attributes['name']} does "
                         f"not have access to this project.")
            sys.exit(1)
        logger.info(f"Connected to gitlab project {project.attributes['path_with_namespace']}")
        return project

    def open_gitlab_group(self, group_name: str) -> GitlabGroup:
        return GitlabGroup(self.gitlab_connection, group_name)
