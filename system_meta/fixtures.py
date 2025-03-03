"""Fixtures for system metadata."""

import pytest

from system_meta.factories import IntegratedSystemFactory


@pytest.fixture
def integrated_system():
    """Create an integrated system."""
    return IntegratedSystemFactory()
