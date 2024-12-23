# Events

Certain operations within Unified Ecommerce trigger events, and those events are sent to the integrated systems.

The integrated system model has a field for a webhook URL. Data for all events are sent to this URL. The integrated system itself decides whether or not to take action on the data.

## Events

These are the events that are triggered:

| Event (in UE) | Type         | Description                                                      |
| ------------- | ------------ | ---------------------------------------------------------------- |
| `basket_add`  | `presale`    | Triggered when an item is added to the basket.                   |
| `post_sale`   | `postsale`   | Triggered when an order has been completed successfully.         |
| `post_refund` | `postrefund` | Triggered when an item has been refunded from a completed order. |

```{note}
The Event tracks the plugin hook that is called to generate the event.
```

## Data Sent

The event data is wrapped in a standard container (implemented in `payments/serializers/v0` as the `WebhookBase` dataclass):

- `system_slug`: the system slug for the data being sent
- `system_key`: the shared key for the system
- `user`: nested object containing user information
- `type`: the event type (see table above)
- `data`: event-specific data

Each system will only get the data that is relevant to itself, which will be indicated by the `system_slug` attribute. The system should verify the slug and key sent are valid, and emit a 401 error if they aren't.

User data includes:

- `id`: the ID of the purchaser (this is Unified Ecommerce's ID)
- `username`: the username of the purchaser (this will be a UUID corresponding to a Keycloak user)
- `email`: the email address of the purchaser
- `first_name`: the purchaser's first name
- `last_name`: the purchaser's last name

The `data` attribute differs depending on what event is being sent.

For `presale`:

- `action`: either "add" or "remove"
- `product`: the product added or removed to the basket

For `postsale`:

- `reference_number`: the reference number of the order. (Despite this saying "number" this is generally a string.)
- `total_price_paid`: the total amount paid for the order, inclusive of any discounts and taxes assessed.
- `state`: the state of the order. This should always be `fulfilled`.
- `lines`: array of line items for the order

`Line` data includes:

- `id`: an ID for the line item
- `quantity`: quantity on order
- `item_description`: description of the item
- `unit_price`: the unit price (before tax/discounts) of the item
- `total_price`: the amount charged for the item
- `product`: the product

`Product` data includes (just relevant fields):

- `id`: an ID for the product
- `sku`: the product's SKU. By convention, this should be the readable ID of the resource in the integrated system.
- `name`: the product's name
- `description`: the product's description
- `system_data`: JSON; system-specific data. This is defined by the integrated system.
- `price`: the base price of the product

## Architecture

Internally, the system uses Pluggy to dispatch events. New events can be added by defining a new hook implementation for the event types listed above.

Events in UE don't necessarily trigger webhook notifications - `basket_add`, for instance, is mostly used to ensure the user can purchase the item and to assess tax if necessary.
