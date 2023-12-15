"""Tests for the add_system command"""

from io import StringIO

import pytest
from django.core.management import call_command
from factory import fuzzy

from system_meta.models import IntegratedSystem

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("withDescription", [True, False])
@pytest.mark.parametrize("withDeactivate", [True, False])
def test_add_system(withDescription, withDeactivate):
    """Tests that add_system adds a system"""
    out = StringIO()

    desc = str(fuzzy.FuzzyText()) if withDescription else ""

    call_command(
        "add_system",
        "test_system",
        description=desc,
        deactivate=withDeactivate,
        stdout=out,
    )
    assert "Successfully created integrated system test_system" in out.getvalue()

    created_system = IntegratedSystem.objects.get(name="test_system")
    assert created_system.description == desc
    assert created_system.is_active != withDeactivate
