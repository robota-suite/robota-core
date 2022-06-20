"""Test for functions in the robota_tools.py file"""
import pathlib
import pytest

import robota_core.config_readers as config_readers

TEST_DIR = pathlib.Path(__file__).parent
ROOT_DIR = TEST_DIR.parent.parent.parent
TEST_FOLDER = TEST_DIR / pathlib.Path("sample_files")
REPO_URL = "https://gitlab.cs.man.ac.uk/institute-of-coding-team/comp23412-robota-config.git"


class TestGetRobotaConfig:
    """Test the functions in the robota_core.robota_tools.GetRobotaConfig class"""
    @staticmethod
    @pytest.mark.config_path
    def test_get_config_bad():
        """Integration test to check exception is thrown when an unknown type is loaded."""
        dummy_config_path = "/dev/null"
        with pytest.raises(config_readers.RobotaConfigLoadError):
            _ = config_readers.get_config(["config.yaml"], {"type": "aaaaaa",
                                                            "directory": dummy_config_path})


class TestReadConfigFile:
    """Test the functions in robota_core.robota_tools._ReadConfigFile"""
    @staticmethod
    def test_yaml_file_read():
        """Test that a valid yaml file can be read"""
        test_config_path = TEST_FOLDER / pathlib.Path("config.yaml")
        config = config_readers.read_yaml_file(test_config_path)
        assert isinstance(config, dict)
        assert config["Name"] == "Fred"
        assert config["Year"] == 2019

    @staticmethod
    def test_config_parser_valid():
        """Check the parse_config method with a valid file type"""
        test_config_path = TEST_FOLDER / pathlib.Path("config.yaml")
        config = config_readers.parse_config(test_config_path)

        assert config["Name"] == "Fred"
        assert config["Year"] == 2019

    @staticmethod
    def test_config_parser_invalid():
        """Check an exception is raised if an invalid file type is passed."""
        with pytest.raises(config_readers.RobotaConfigParseError):
            bad_config_path = TEST_FOLDER / pathlib.Path("another_config.txt")
            _ = config_readers.parse_config(bad_config_path)
