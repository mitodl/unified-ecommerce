"""Tests for the add_system command"""

from io import StringIO

import pytest
from django.core.management import call_command
from factory import fuzzy

from system_meta.models import IntegratedSystem

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("with_description", [True, False])
@pytest.mark.parametrize("with_deactivate", [True, False])
def test_add_system(with_description, with_deactivate):
    """Tests that add_system adds a system"""
    out = StringIO()

    desc = str(fuzzy.FuzzyText()) if with_description else ""

    call_command(
        "add_system",
        "test_system",
        description=desc,
        deactivate=with_deactivate,
        stdout=out,
    )
    assert "Successfully created integrated system test_system" in out.getvalue()

    created_system = IntegratedSystem.all_objects.get(name="test_system")
    assert created_system.description == desc
    if with_deactivate:
        assert not created_system.is_active
        assert created_system.deleted_on is not None
    else:
        assert created_system.is_active
        assert created_system.deleted_on is None
