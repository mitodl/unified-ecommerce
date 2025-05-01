# pylint: disable=wildcard-import, unused-wildcard-import
from unittest.mock import Mock, patch

import pytest
from django.conf import settings

from fixtures.common import *  # noqa: F403
from fixtures.users import *  # noqa: F403
from unified_ecommerce.exceptions import DoNotUseRequestException


@pytest.fixture(autouse=True)
def mock_requests_get():
    # Mock the response of requests.get
    with patch("system_meta.tasks.requests.get") as mock_get:
        # Create a mock response object
        mock_response = Mock()
        mock_response.raise_for_status = Mock()  # Mock the raise_for_status method
        mock_response.json.return_value = {
            "results": [
                {
                    "image": {
                        "url": "http://example.com/image.jpg",
                        "alt": "Image alt text",
                        "description": "Image description",
                    }
                }
            ]
        }
        mock_get.return_value = (
            mock_response  # Set the mock response to be returned by requests.get
        )
        yield mock_get  # This will be the mocked requests.get


@pytest.fixture(autouse=True)
def _prevent_requests(mocker, request):
    """Patch requests to error on request by default"""
    if "mocked_responses" in request.fixturenames:
        return
    mocker.patch(
        "requests.sessions.Session.request",
        autospec=True,
        side_effect=DoNotUseRequestException,
    )


@pytest.fixture(autouse=True)
def _fix_prefix_for_testing():
    """Fix the API path prefix for testing - it should be empty"""

    settings.MITOL_APP_PATH_PREFIX = ""
