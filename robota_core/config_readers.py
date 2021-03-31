from loguru import logger
import os
import pathlib
import re
import shutil
import stat
import tempfile
import tarfile
import csv
from typing import List, Tuple, Union

import gitlab
import yaml

from robota_core import gitlab_tools as gitlab_tools


class RobotaConfigLoadError(Exception):
    """The error raised when there is a problem loading the configuration"""


class RobotaConfigParseError(Exception):
    """The error raised when there is a problem parsing the configuration"""


def get_config(file_names: Union[str, List[str]], data_source: dict) -> list:
    """The base method of the class. Calls different methods to get the config
    depending on the config type.

    :param file_names: The names of one or more config files to open.
    :param data_source: Information about the source of the config data. The 'type' key specifies
      the source of the data and other keys are extra information about the source like url
      or API token.
    :return: a list of parsed file contents, one list element for each file specified in
      `file_names`. If a file is not found, the corresponding list element is set to None.
    """
    if isinstance(file_names, str):
        file_names = [file_names]

    if not isinstance(data_source, dict):
        raise TypeError("Config variables must be a dictionary of variables.")
    source_type = data_source["type"]

    if source_type == "local_path":
        parsed_variables = _config_from_local_path(data_source, file_names)
    elif source_type == "gitlab":
        parsed_variables = _config_from_gitlab(data_source, file_names)
    else:
        raise RobotaConfigLoadError(f"Source type: {source_type} is not a valid data source for"
                                    f" the 'get_config' method.")

    return parsed_variables


def _config_from_gitlab(data_source, file_names) -> List[dict]:
    parsed_variables = []

    config_file_directory, commit_id = get_gitlab_config(data_source)
    for name in file_names:
        config_path = config_file_directory / pathlib.Path(name)
        if config_path.is_file():
            file_contents = parse_config(config_path)
            if isinstance(file_contents, dict):
                file_contents["config_commit_id"] = commit_id
            parsed_variables.append(file_contents)
        else:
            parsed_variables.append(None)
    if config_file_directory:
        shutil.rmtree(config_file_directory, onerror=rmtree_error)
    return parsed_variables


def _config_from_local_path(data_source, file_names) -> List[dict]:
    parsed_variables = []

    for name in file_names:
        config_path = pathlib.Path(data_source["path"]) / pathlib.Path(name)
        if config_path.exists():
            config = parse_config(config_path)
            parsed_variables.append(config)
        else:
            logger.warning(f"Attempted to load config from path: '{config_path}', "
                           f"but path does not exist.")
            parsed_variables.append(None)
    return parsed_variables


def get_gitlab_config(config_variables: dict) -> Tuple[pathlib.Path, str]:
    """Get config from a Gitlab repository by logging in using an access token and downloading
    the files from the repository.

    :param config_variables: required keys/value pairs are:
      gitlab_url: The URL  of the gitlab repository
      gitlab_project: The full project name of the project containing the config files.
      gitlab_token: The gitlab access token.
    :return: the temporary directory containing the config files.
    """
    # Read GitLab authentication token stored as environment variable
    if "token" in config_variables:
        token = config_variables["token"]
    else:
        token = None

    gitlab_server = gitlab_tools.GitlabServer(config_variables["url"], token)
    if "branch" in config_variables:
        branch_name = config_variables["branch"]
    else:
        branch_name = "master"

    project = gitlab_server.open_gitlab_project(config_variables["project"])
    try:
        commit_id = project.commits.get(branch_name).attributes["short_id"]
    except gitlab.exceptions.GitlabGetError:
        raise gitlab.exceptions.GitlabGetError(f"Error fetching config. "
                                               f"Branch {branch_name} not found in "
                                               f"repository: {config_variables['project']}.")
    temp_path = pathlib.Path(tempfile.mkdtemp())
    tar_path = temp_path / pathlib.Path("tar")
    with open(tar_path, 'wb') as output_dir:
        output_dir.write(project.repository_archive(branch_name))
    with tarfile.TarFile.open(tar_path, mode='r') as input_tar:
        input_tar.extractall(temp_path)
    for file in temp_path.iterdir():
        if file.name != "tar":
            return file, commit_id


def read_csv_file(csv_path: Union[str, pathlib.Path]) -> dict:
    """Parse a two column csv file. Return dict with first column as keys and second column
    as values.
    """
    data = {}
    with open(csv_path, newline='') as f:
        reader = csv.reader(f, skipinitialspace=True)
        for row in reader:
            if row:
                data[row[0]] = row[1]

    return data


def process_yaml(yaml_content: dict) -> dict:
    """Do custom string substitution to the dictionary produced from reading a YAML file.
    This is not part of the core YAML spec.
    This function replaces instances of ${key_name} in strings nested as values in dicts or lists
    with the value of the key "key_name" if "key_name" occurs in the root of the dictionary.
    """

    if isinstance(yaml_content, dict):
        # Collect all of the highest level values in the dict - these can be used for substitution
        # elsewhere
        root_keys = {}
        for key, value in yaml_content.items():
            if not isinstance(value, list) and not isinstance(value, dict):
                root_keys.update({key: value})

        for key, value in yaml_content.items():
            yaml_content[key] = substitute_dict(value, root_keys)
    return yaml_content


def substitute_dict(input_value: object, root_keys: dict) -> object:
    """If `input_value` is a list or dict, recurse into it trying to find strings.
    If `input_value` is a string then substitute any variables that occur as keys in `root_keys`
    with the values in `root_keys`.
    Variables to be substituted are indicated by a bash like syntax, e.g. ${variable_name}."""

    if isinstance(input_value, list):
        for item in input_value:
            input_value[input_value.index(item)] = substitute_dict(item, root_keys)
    if isinstance(input_value, dict):
        for key, value in input_value.items():
            input_value[key] = substitute_dict(value, root_keys)
    if isinstance(input_value, str):
        sub_keys = re.findall(r"(?<=\${)([^}]*)(?=})", input_value)
        for key in sub_keys:
            if key in root_keys:
                input_value = input_value.replace(f"${{{key}}}", str(root_keys[key]))
    return input_value


def parse_config(config_path: pathlib.Path) -> dict:
    """Parses a config file to extract the configuration variables from it.

    :param config_path: the full file path to the config file.
    :return: the config variables read from the file. Return type depends on the file type.
    """
    config_file_type = config_path.suffix

    if config_file_type in [".yaml", ".yml"]:
        config = read_yaml_file(config_path)
        config = process_yaml(config)
    elif config_file_type == ".csv":
        config = read_csv_file(config_path)
    else:
        raise RobotaConfigParseError(f"Cannot parse file of type: {type}.")

    return config


def read_yaml_file(config_location: pathlib.Path) -> dict:
    """ Read a YAML file into a dictionary

    :param config_location: the path of the config file
    :return: Key-value pairs from the config file
    """
    # noinspection PyTypeChecker
    with open(config_location, encoding='utf8') as yaml_file:
        try:
            config = yaml.load(yaml_file.read(), Loader=yaml.FullLoader)
        except yaml.YAMLError as e:
            logger.error(f"YAML Parsing of file {config_location.absolute()} failed.")
            raise e
    return config


def get_robota_config(config_path: str, substitution_vars: dict) -> dict:
    """The robota config specifies the source for each data type used by RoboTA. The RoboTA
    config is always stored locally since it contains API tokens.
    :param config_path: The path of the robota config file to read.
    :param substitution_vars: An optional dictionary of values to substitute into the config file.
    """
    config_path = pathlib.Path(config_path)

    # Load RoboTA config from file.
    robota_config = get_config([config_path.name], {"type": "local_path",
                                                    "path": config_path.parent})[0]
    if robota_config is None:
        raise RobotaConfigLoadError(f"Unable to load robota config from {config_path.absolute()}")
    logger.debug(f"robota-config loaded from {config_path.absolute()}")

    return substitute_keys(robota_config, substitution_vars)


def substitute_keys(robota_config: dict, command_line_args: dict) -> dict:
    """Go through all of the data sources replacing any curly bracketed strings by named
    variables provided to roboTA as command line arguments. This allows substitution of things
    like a team name or exercise number into the robota config.

    :param robota_config: The dictionary of data sources loaded from robota-config.yaml.
    :param command_line_args: Command line arguments given to RoboTA.
    """
    for top_key in ["data_types", "data_sources"]:
        for source_name, data_source in robota_config[top_key].items():
            for key, value in data_source.items():
                if not value:
                    raise KeyError(f"Key '{key}' in robota config has no value.")
                for name, arg in command_line_args.items():
                    if f"{{{name}}}" in value:
                        robota_config[top_key][source_name][key] = robota_config[top_key][source_name][key].replace(f"{{{name}}}", arg)

    return robota_config


def get_data_source_info(robota_config: dict, key: str) -> Union[dict, None]:
    """Get the information about the data source specified by 'key' from the robota_config
    dictionary."""
    config_error = "Error in RoboTA config file."
    if "data_types" not in robota_config:
        raise RobotaConfigParseError(f"{config_error} 'data_types' section not found in "
                                     f"robota-config.")
    if key not in robota_config["data_types"]:
        logger.debug(f"'{key}' not found in 'data_types' config section. Not initialising "
                     f"this data source.")
        return None
    data_type_info = robota_config["data_types"][key]
    if "data_source" not in data_type_info:
        raise RobotaConfigParseError(f"{config_error} 'data_source' key not found in details "
                                     f"of '{key}' data type in robota_config.")
    data_source = data_type_info["data_source"]
    if "data_sources" not in robota_config:
        raise RobotaConfigParseError(f"{config_error} 'data_sources section not found.")
    if data_source not in robota_config["data_sources"]:
        raise RobotaConfigParseError(f"{config_error} Data source '{data_source}' specified in "
                                     f"'data_types' section, but no details provided in "
                                     f"'data_sources' section.")
    data_source_info = robota_config["data_sources"][data_source]
    if "type" not in data_source_info:
        raise RobotaConfigParseError(f"Error in RoboTA config file. 'type' not specified in "
                                     f"data source: '{data_source}'.")
    return {**data_source_info, **data_type_info}


def rmtree_error(func, path, _):
    """Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file) it attempts to add write
    permission and then retries.
    """
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)
