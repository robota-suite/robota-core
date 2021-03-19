from robota_core.config_readers import process_yaml


class TestProcessYaml:
    @staticmethod
    def test_root_dict_substitution():
        """The key to be substituted is in the top level of the dictionary."""
        initial = {"name": "Peter", "greeting": "Hello ${name}"}
        expected = {"name": "Peter", "greeting": "Hello Peter"}

        actual = process_yaml(initial)
        assert actual == expected

    @staticmethod
    def test_root_dict_substitution_with_int():
        """The key to be substituted is an integer in the top level of the dictionary."""
        initial = {"name": 7, "greeting": "Hello ${name}"}
        expected = {"name": 7, "greeting": "Hello 7"}

        actual = process_yaml(initial)
        assert actual == expected

    @staticmethod
    def test_double_root_dict_substitution():
        """The key to be substituted occurs twice in the top level of the dictionary."""
        initial = {"name": "Peter", "greeting": "Hello ${name} ${name}"}
        expected = {"name": "Peter", "greeting": "Hello Peter Peter"}

        actual = process_yaml(initial)
        assert actual == expected

    @staticmethod
    def test_different_double_root_dict_substitution():
        """Two different keys are substituted in the top level of the dictionary."""
        initial = {"name1": "Peter", "name2": "Fred", "greeting": "Hello ${name1} ${name2}"}
        expected = {"name1": "Peter", "name2": "Fred", "greeting": "Hello Peter Fred"}

        actual = process_yaml(initial)
        assert actual == expected

    @staticmethod
    def test_second_level_dict_substitution():
        """The key to be substituted occurs nested inside another top level dictionary."""
        initial = {"name": "Peter", "greetings": {"arrival": "Hello ${name}",
                                                  "departure": "Goodbye ${name}"}}
        expected = {"name": "Peter", "greetings": {"arrival": "Hello Peter",
                                                   "departure": "Goodbye Peter"}}
        actual = process_yaml(initial)
        assert actual == expected

    @staticmethod
    def test_second_level_list_substitution():
        """The key to be substituted is in a list inside a top level dictionary."""
        initial = {"name": "Peter", "greeting": ["Hello ${name}", 7]}
        expected = {"name": "Peter", "greeting": ["Hello Peter", 7]}

        actual = process_yaml(initial)
        assert actual == expected

    @staticmethod
    def test_only_top_level_keys():
        """Key substitution only works with top level keys."""
        initial = {"name": {"sub-key": "Ahoy!"}, "greeting": "Hello ${sub-key}"}

        actual = process_yaml(initial)
        assert actual == initial

    @staticmethod
    def test_ignore_list():
        """YAML files can be returned as lists if there are no root keys. The function should
        ignore lists as an input."""
        initial = ["Some data", "more ${data}"]

        actual = process_yaml(initial)
        assert actual == initial
