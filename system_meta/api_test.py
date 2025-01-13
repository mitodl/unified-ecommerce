"""Tests for the system_meta APIs."""

import pytest

from system_meta.api import update_product_metadata
from system_meta.factories import ProductFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("valid_run", [True, False])
def test_retrieve_product_metadata(mocker, valid_run):
    """Test that the retrieve_product_metadata function works."""

    mocked_requests = mocker.patch("requests.get")
    mocked_requests.return_value.json.return_value = {
        "count": 1,
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
                        "run_id": "course-v1:MITx+12.345x+2T2099",
                        "prices": [150, 250],
                    }
                ]
                if valid_run
                else [],
            }
        ],
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
    assert product.price == 250 if valid_run else 200


def test_retrieve_product_metadata_no_match(mocker):
    """Test that the retrieve_product_metadata function works when no data exists in Learn.."""

    mocked_requests = mocker.patch("requests.get")
    mocked_requests.return_value.json.return_value = {"count": 0, "results": []}

    product = ProductFactory.create(
        sku="course-v1:MITx+12.345x+2T2099",
        price=50,
        description="This is the wrong description.",
    )
    update_product_metadata(product.id)
    product.refresh_from_db()
    assert product.description == "This is the wrong description."
    assert product.price == 50
