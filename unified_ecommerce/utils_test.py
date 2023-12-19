"""Utils tests"""

import datetime
from tempfile import NamedTemporaryFile

import pytest
from django.contrib.auth import get_user_model

from unified_ecommerce.factories import UserFactory
from unified_ecommerce.utils import (
    extract_values,
    filter_dict_keys,
    filter_dict_with_renamed_keys,
    html_to_plain_text,
    markdown_to_plain_text,
    merge_strings,
    normalize_to_start_of_day,
    prefetched_iterator,
    write_to_file,
)

User = get_user_model()


def test_normalize_to_start_of_day():
    """
    Test that normalize_to_start_of_day zeroes out the time components
    """
    assert normalize_to_start_of_day(
        datetime.datetime(2018, 1, 3, 5, 6, 7)  # noqa: DTZ001
    ) == datetime.datetime(  # noqa: DTZ001
        2018, 1, 3
    )


@pytest.mark.parametrize(
    ("list_or_string", "output"),
    [
        ["str", ["str"]],  # noqa: PT007
        [["str", None, [None]], ["str"]],  # noqa: PT007
        [[["a"], "b", ["c", "d"], "e"], ["a", "b", "c", "d", "e"]],  # noqa: PT007
    ],
)
def test_merge_strings(list_or_string, output):
    """
    merge_strings should flatten a nested list of strings
    """
    assert merge_strings(list_or_string) == output


def test_filter_dict_keys():
    """filter_dict_keys should return a dict with only the specified list of keys"""
    d = {"a": 1, "b": 2, "c": 3, "d": 4}
    assert filter_dict_keys(d, ["b", "d"]) == {"b": 2, "d": 4}

    with pytest.raises(KeyError):
        assert filter_dict_keys(d, ["b", "missing"])

    assert filter_dict_keys(d, ["b", "missing"], optional=True) == {"b": 2}


def test_filter_dict_with_renamed_keys():
    """
    filter_dict_with_renamed_keys should return a dict with only the keys in a filter dict,
    and should rename those keys according to the values in the filter dict.
    """
    d = {"a": 1, "b": 2, "c": 3, "d": 4}
    assert filter_dict_with_renamed_keys(d, {"b": "b1", "d": "d1"}) == {
        "b1": 2,
        "d1": 4,
    }

    with pytest.raises(KeyError):
        assert filter_dict_with_renamed_keys(d, {"b": "b1", "missing": "d1"})

    assert filter_dict_with_renamed_keys(
        d, {"b": "b1", "missing": "d1"}, optional=True
    ) == {"b1": 2}


def test_html_to_plain_text():
    """
    html_to_plain_text should turn a string with HTML markup into plain text with line breaks
    replaced by spaces.
    """
    html = "<div><b>bold</b><p>text with\n\nline breaks</p></div>"
    normal_text = "open discussions"
    assert html_to_plain_text(html) == "boldtext with  line breaks"
    assert html_to_plain_text(normal_text) == normal_text


def test_markdown_to_plain_text():
    """
    markdown_to_plain_text should turn a Markdown string into plain text with line breaks
    replaced by spaces.
    """
    markdown = "# header\n\nsome body text\n\n1. bullet 1\n2. bullet 2"
    normal_text = "open discussions"
    assert (
        markdown_to_plain_text(markdown) == "header some body text  bullet 1 bullet 2"
    )
    assert html_to_plain_text(normal_text) == normal_text


@pytest.mark.django_db()
@pytest.mark.parametrize("chunk_size", [2, 3, 5, 7, 9, 10])
def test_prefetched_iterator(chunk_size):
    """
    prefetched_iterator should yield all items in the record set across chunk boundaries
    """
    users = UserFactory.create_batch(10)
    fetched_users = list(prefetched_iterator(User.objects.all(), chunk_size=chunk_size))
    assert len(users) == len(fetched_users)
    for user in users:
        assert user in fetched_users


def test_extract_values():
    """
    extract_values should return the correct match from a dict
    """
    test_json = {
        "a": {"b": {"c": [{"d": [1, 2, 3]}, {"d": [4, 5], "e": "f", "b": "g"}]}}
    }
    assert extract_values(test_json, "b") == [test_json["a"]["b"], "g"]
    assert extract_values(test_json, "d") == [[1, 2, 3], [4, 5]]
    assert extract_values(test_json, "e") == ["f"]


def test_write_to_file():
    """Test that write_to_file creates a file with the correct contents"""
    content = (
        b"-----BEGIN"
        b" CERTIFICATE-----\nMIID5DCCA02gAwIBAgIRTUTVwsj4Vy+l6+XTYjnIQ==\n-----END"
        b" CERTIFICATE-----"
    )
    with NamedTemporaryFile() as outfile:
        write_to_file(outfile.name, content)
        with open(outfile.name, "rb") as infile:  # noqa: PTH123
            assert infile.read() == content
