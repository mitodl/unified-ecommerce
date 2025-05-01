"""Fixtures for system metadata."""

import pytest

from system_meta.factories import IntegratedSystemFactory


@pytest.fixture()  # noqa: PT001, RUF100
def integrated_system():
    """Create an integrated system."""
    return IntegratedSystemFactory()
