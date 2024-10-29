"""Dataclasses for the payments app."""

from dataclasses import dataclass

from authentication.dataclasses import CustomerCalculatedLocation


@dataclass
class CustomerLocationMetadata:
    """The customer's location."""

    location_block: CustomerCalculatedLocation
    location_tax: CustomerCalculatedLocation
