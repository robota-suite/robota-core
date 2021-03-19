import datetime
import re
from typing import Union, Dict

import bleach
import markdown


def string_to_datetime(date: Union[str, None],
                       datetime_format: str = '%Y-%m-%dT%H:%M:%S.%fZ') -> Union[datetime.datetime,
                                                                                None]:
    """Convert time string (output from GitLab project attributes) to datetime.

    :param date: A string representing the datetime.
    :param datetime_format: The format of 'date'.
    :return date: The converted datetime.

    >>> string_to_datetime('2017-12-06T08:28:32.000Z', "%Y-%m-%dT%H:%M:%S.%fZ")
    datetime.datetime(2017, 12, 6, 8, 28, 32)
    """
    if date is None:
        return None
    if isinstance(date, str):
        return datetime.datetime.strptime(date, datetime_format)
    else:
        raise TypeError("Unknown date type. Cannot convert.")


def markdownify(text: str) -> str:
    """Take text in markdown format and output the formatted text with HTML markup."""
    return markdown.markdown(text, extensions=['attr_list'])


def clean(text: str) -> str:
    """Convert any HTML tags to a string representation so HTML cannot be executed."""
    return bleach.clean(text)


def html_newlines(text: str) -> str:
    """Replace any newline characters in a string with html newline characters."""
    html = re.sub('(\n)+', '<br>', text)
    return html


def list_to_html_rows(list_of_strings: list) -> str:
    """Join list items with html new lines."""
    return '<br>'.join(list_of_strings)


def sublist_to_html_rows(list_of_lists: list, empty='-') -> list:
    """Separate items in a sub-list by html new lines instead of commas."""
    for item in list_of_lists:
        assert item is None or isinstance(item, list)

    return [list_to_html_rows(list_items) if list_items else empty
            for list_items in list_of_lists]


def get_link(url: str, link_text: Union[str, int, float]) -> str:
    """Create link (e.g. to a commit)."""

    return f'<a target="_parent" href="{url}">{link_text}</a>'


def build_regex_string(string: str) -> str:
    """Escape some characters and replace * and ? wildcard characters with the
    python regex equivalents."""
    string.replace(".", r"\.")
    string.replace("*", ".+")
    string.replace("?", ".")
    return string


def replace_none(input_list: list, replacement='-') -> list:
    """Sanitise list for display purposes."""
    return [item if item is not None else replacement for item in input_list]


def append_list_to_dict(dictionary: Dict[str, list], key: str, value: list):
    """If key exists in dictionary then append value to it, else add a new key with value.

    :param dictionary: A dictionary to add key and value to.
    :param key: Dictionary key.
    :param value: A value to append to the dictionary list.
    """
    if key in dictionary:
        dictionary[key].extend(value)
    else:
        dictionary[key] = value
