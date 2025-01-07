"""Tests for the system_meta APIs."""

import pytest

from system_meta.api import update_product_metadata
from system_meta.factories import ProductFactory

pytestmark = pytest.mark.django_db


def test_retrieve_product_metadata(mocker):
    """Test that the retrieve_product_metadata function works."""

    mocked_requests = mocker.patch("requests.get")
    mocked_requests.return_value.json.return_value = {
        "results": [
            {
                "image": {
                    "id": 12345,
                    "url": "https://example.com/image.jpg",
                    "alt": "Example image",
                    "description": "Example description",
                },
                "title": "Example title",
                "description": "Example description",
                "prices": [100, 200],
                "readable_id": "course-v1:MITx+12.345x",
                "runs": [
                    {
                        "run_id": "123",
                        "prices": [150, 250],
                        "readable_id": "course-v1:MITx+12.345x+2T2099",
                    }
                ],
            }
        ]
    }

    product = ProductFactory.create(
        sku="course-v1:MITx+12.345x+2T2099",
        price=50,
        description="This is the wrong description.",
    )
    update_product_metadata(product.id)
    product.refresh_from_db()
    assert product.image_metadata is not None
    assert product.name == "Example title"
    assert product.description == "Example description"
    # This has a run price, so we should have that, and it should be the highest price.
    assert product.price == 250
