# pylint: disable=wildcard-import, unused-wildcard-import
from unittest.mock import patch

import pytest

from fixtures.common import *  # noqa: F403
from fixtures.users import *  # noqa: F403
from system_meta.models import Product
from unified_ecommerce.exceptions import DoNotUseRequestException


@pytest.fixture(autouse=True)
def mock_api_request():
    """
    Mock the API request to prevent actual API calls during tests.
    """
    # Mock the requests.get method to prevent actual API calls during tests
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "results": [
                {
                    "image": {
                        "url": "test_url",
                        "alt": "test_alt",
                        "description": "test_description",
                    }
                }
            ]
        }
        yield mock_get  # Yield the mock for use in the test


@pytest.fixture()
def product():
    """
    Create a Product instance for testing purposes
    """
    # Create and return an instance of MyModel
    return Product()


@pytest.fixture(autouse=True)
def prevent_requests(mocker, request):  # noqa: PT004
    """Patch requests to error on request by default"""
    if "mocked_responses" in request.fixturenames:
        return
    mocker.patch(
        "requests.sessions.Session.request",
        autospec=True,
        side_effect=DoNotUseRequestException,
    )
