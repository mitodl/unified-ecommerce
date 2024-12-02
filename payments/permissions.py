from rest_framework_api_key.permissions import BaseHasAPIKey
from system_meta.models import IntegratedSystemAPIKey


class HasIntegratedSystemAPIKey(BaseHasAPIKey):
    model = IntegratedSystemAPIKey
