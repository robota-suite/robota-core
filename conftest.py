# This provides configuration for PyTest when it runs in this directory.
import pytest


def pytest_addoption(parser):
    parser.addoption("--config_path", default=None, help="The path to the RoboTA config file")
    parser.addoption("--max_team_num", default=None, help="The number of teams over which to run "
                                                          "the integration tests.")
    parser.addoption("--ex_nums", default=None, help="The number of exercises over which to run"
                                                     "the integration tests as a comma "
                                                     "delimited string.")


@pytest.fixture(scope="session")
def config_path(pytestconfig):
    return pytestconfig.getoption("--config_path", skip=True)


@pytest.fixture(scope="session")
def max_exercise_number(pytestconfig):
    return pytestconfig.getoption("--ex_nums", skip=True).split(",")


def pytest_generate_tests(metafunc):
    if "team_number" in metafunc.fixturenames:
        if metafunc.config.getoption("max_team_num"):
            max_team_num = int(metafunc.config.getoption("max_team_num"))
            metafunc.parametrize("team_number", range(1, max_team_num + 1))
    if "exercise_number" in metafunc.fixturenames:
        if metafunc.config.getoption("ex_nums"):
            ex_nums = metafunc.config.getoption("ex_nums").split(",")
            ex_nums = [num.strip() for num in ex_nums]
            metafunc.parametrize("exercise_number", ex_nums)
