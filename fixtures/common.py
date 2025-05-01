"""Common config for pytest and friends"""

# pylint: disable=unused-argument, redefined-outer-name
import logging
import warnings
from types import SimpleNamespace

import factory
import pytest
import responses
from pytest_mock import PytestMockWarning
from rest_framework.test import APIClient
from urllib3.exceptions import InsecureRequestWarning


@pytest.fixture(autouse=True)
def silence_factory_logging():
    """Only show factory errors"""
    logging.getLogger("factory").setLevel(logging.ERROR)


@pytest.fixture(autouse=True)
def warnings_as_errors():
    """
    Convert warnings to errors. This should only affect unit tests, letting pylint and other plugins
    raise DeprecationWarnings without erroring.
    """  # noqa: E501
    try:
        warnings.resetwarnings()
        warnings.simplefilter("error")
        # For celery
        warnings.simplefilter("ignore", category=ImportWarning)
        warnings.filterwarnings("ignore", category=InsecureRequestWarning)
        warnings.filterwarnings("ignore", category=PytestMockWarning)
        warnings.filterwarnings("ignore", category=ResourceWarning)
        warnings.filterwarnings(
            "ignore",
            message="'async' and 'await' will become reserved keywords in Python 3.7",
            category=DeprecationWarning,
        )
        # Ignore deprecation warnings in third party libraries
        warnings.filterwarnings(
            "ignore",
            module=".*(api_jwt|api_jws|rest_framework_jwt|astroid|celery|factory).*",
            category=DeprecationWarning,
        )
        yield
    finally:
        warnings.resetwarnings()


@pytest.fixture
def randomness():
    """Ensure a fixed seed for factoryboy"""
    factory.fuzzy.reseed_random("happy little clouds")


@pytest.fixture
def mocked_celery(mocker):
    """Mock object that patches certain celery functions"""
    exception_class = TabError
    replace_mock = mocker.patch(
        "celery.app.task.Task.replace", autospec=True, side_effect=exception_class
    )
    group_mock = mocker.patch("celery.group", autospec=True)
    chain_mock = mocker.patch("celery.chain", autospec=True)

    return SimpleNamespace(
        replace=replace_mock,
        group=group_mock,
        chain=chain_mock,
        replace_exception_class=exception_class,
    )


@pytest.fixture
def mock_context(mocker, user):
    """Mock context for serializers"""
    return {"request": mocker.Mock(user=user)}


@pytest.fixture
def mocked_responses():
    """Mock responses fixture"""
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def admin_drf_client(admin_user):
    """DRF API test client with admin user"""
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture(autouse=True)
def mock_learn_api_metadata_updater(mocker):
    """Mock out the call to update products from the Learn API"""

    return {
        "update_product_metadata": mocker.patch(
            "system_meta.api.update_product_metadata"
        ),
        "update_products_task": mocker.patch("system_meta.tasks.update_products.delay"),
    }
