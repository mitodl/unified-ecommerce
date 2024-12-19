# Events

Unified Ecommerce emits events when certain transaction states are hit. These are emitted to the relevant integrated system as a hit to a configured webhook.

## Data Sent

The data that gets sent is:

* `reference_number` - the reference number for the order
* `system_slug` - the system slug for the data being sent
* `user` - nested object containing user information
* `total_price_paid` - the total price paid for the order, inclusive of _all_ items on the order
* `state` - the order state
* `lines` - line items in the order

Each system will only get the data that is relevant to itself, which will be indicated by the `system_slug` attribute. If the slug does not match what the system expects, the webhook target should return a 500 response so that Unified Ecommerce can log a Sentry error.

To that end, the `lines` attribute will only include the line items that are for the system that UE is talking to. Totalling the line cost will not necessarily match the `total_price_paid` value as the total may include line items not visible to the system.

User data includes:

* `username` - the username of the purchaser
* `email` - the email address of the purchaser
* `first_name` - the purchaser's first name
* `last_name` - the purchaser's last name

Individual line items include:

* `quantity` - the number of items purchased for this line (this will generally be one)
* `discounted_price` - the discounted price of the line item
* `product_sku` - the line item's SKU
* `system_data` - the line item's system data

Products configured in the Universal Ecommerce system can contain system-specific data in JSON format - that is what is returned in the `system_data` attribute.
