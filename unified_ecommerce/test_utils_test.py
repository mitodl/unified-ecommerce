"""Tests for test utils"""

import pickle

import pytest

from unified_ecommerce.test_utils import (
    MockResponse,
    PickleableMock,
    any_instance_of,
    assert_json_equal,
    assert_not_raises,
)


def test_any_instance_of():
    """Tests any_instance_of()"""
    any_number = any_instance_of(int, float)

    assert any_number == 0.405
    assert any_number == 8_675_309
    assert any_number != "not a number"
    assert any_number != {}
    assert any_number != []


def test_assert_not_raises_none():
    """
    assert_not_raises should do nothing if no exception is raised
    """
    with assert_not_raises():
        pass


def test_assert_not_raises_exception(mocker):
    """assert_not_raises should fail the test"""
    # Here there be dragons
    fail_mock = mocker.patch("pytest.fail", autospec=True)
    with assert_not_raises():
        raise TabError
    assert fail_mock.called is True


def test_assert_not_raises_failure():
    """assert_not_raises should reraise an AssertionError"""
    with pytest.raises(AssertionError), assert_not_raises():
        assert 1 == 2  # pylint:disable=comparison-of-constants  # noqa: PLR0133


def test_mock_response():
    """Assert MockResponse returns correct values"""
    content = "test"
    response = MockResponse(content, 404)
    assert response.status_code == 404
    assert response.decoded_content == content
    assert response.content == content.encode("utf-8")


def test_pickleable_mock():
    """Tests that a mock can be pickled"""
    pickle.dumps(PickleableMock(field_name={}))  # pylint:disable=use-dict-literal


def test_assert_json_equal():
    """Asserts that objects are equal in JSON"""
    assert_json_equal({"a": 1}, {"a": 1})
    assert_json_equal(2, 2)
    assert_json_equal([2], [2])


def test_assert_json_equal_with_timestamps():
    """Assert that objects that have timestamps are equal, outside of their timestamps"""

    obj1 = {
        "a": 1,
        "created_on": "2020-01-01T00:00:00Z",
        "updated_on": "2020-01-01T00:00:00Z",
    }
    obj2 = {
        "a": 1,
        "created_on": "2021-01-01T00:00:00Z",
        "updated_on": "2021-01-01T00:00:00Z",
    }

    assert_json_equal(obj1, obj2, ignore_timestamps=True)

    obj2 = obj1

    assert_json_equal(obj1, obj2, ignore_timestamps=True)
