"""Dataclasses for the users app."""

from dataclasses import dataclass


@dataclass
class CustomerCalculatedLocation:
    """Describes how the customer's location was determined."""

    country_code: str
    lookup_type: str
    ip: str
