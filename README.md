# MIT OL Unified Ecommerce

This application provides a central system to handle ecommerce activities across the Open Learning web applications.

**SECTIONS**

- [MIT OL Unified Ecommerce](#mit-ol-unified-ecommerce)
  - [Initial Setup](#initial-setup)
    - [Configure required `.env` settings](#configure-required-env-settings)
    - [Loading and Accessing Data](#loading-and-accessing-data)
    - [API Access](#api-access)
    - [Managing APISIX](#managing-apisix)
  - [Code Generation](#code-generation)
  - [Committing \& Formatting](#committing--formatting)
  - [Optional Setup](#optional-setup)
    - [Interstitial Debug Mode](#interstitial-debug-mode)
    - [Webhook Retry](#webhook-retry)
    - [Running the app in a notebook](#running-the-app-in-a-notebook)
    - [Change ports](#change-ports)
    - [Import MaxMind GeoIP data](#import-maxmind-geoip-data)

## Initial Setup

Unified Ecommerce follows the same [initial setup steps outlined in the common OL web app guide](https://mitodl.github.io/handbook/how-to/common-web-app-guide.html).
Run through those steps **including the addition of `/etc/hosts` aliases and the optional step for running the
`createsuperuser` command**.

Additionally, you will need a Keycloak instance set up with a realm for the application. The realm can be an existing one - if you have a realm set up for other applications (e.g. Learn), you should use that realm.

If you don't have a Keycloak instance set up, or if you want to test with a known-good configuration, the app can optionally run with its own Keycloak instance. See [README-keycloak.md](README-keycloak.md) for instructions.

### Configure required `.env` settings

The following settings must be configured before running the app:

#### App Settings

- `MITOL_UE_HOSTNAME`

  Sets the hostname required by webpack for building the frontend. Should likely be whatever you set
  the host to in your /etc/hosts or the hostname that you're accessing it from. Likely `api.pay.odl.local`.

- `SECRET_KEY`

  Sets the Django secret for the application. This just needs to be a random string.

- `MITOL_UE_COOKIE_NAME`

  The name to use for the cookie for the app. A good choice is something like `mitolpay-local`.

- `MITOL_USE_COOKIE_DOMAIN`

  The domain to use for the cookie - for local development, use a pretty generic one like `odl.local`.

- `MITOL_UE_PAYMENT_BASKET_ROOT`

  The root URL for the basket page. This defaults to `/cart/` (which is the cart test mule app), but if you're testing the actual frontend, this needs to be set to go there (i.e. `http://pay.odl.local:8072/`). Make sure this has a `/` appended since it is used to _generate_ URLs.

- `MITOL_UE_PAYMENT_BASKET_CHOOSER`

  The URL for an optional "chooser" page. If the `establish_session` call happens without a valid system slug, the user gets sent here so they can choose which cart they want to see. This is usually set to the same as the basket root above.

- `MITOL_UE_PAYMENT_INTERSTITIAL_DEBUG`

  Set to True to get a debug screen when you check out. This gives you an easy way to see the payload that's being sent to CyberSource, and the ability to cancel sending it.

- `MITOL_LEARN_API_URL`

  The URL to use for the Learn API. UE will pull product data from the API here. This can be handy for local testing (to get real products/prices) - if you want to use production, set to `https://api.learn.mit.edu/api/v1/`.

#### APISIX Configuration

- `APISIX_SESSION_SECRET_KEY`

  The secret key that APISIX will use to encode session data. This has a reasonable default, but if you do specify this, make sure the key you specify is _at least_ 16 characters long and is not numeric. (It can contain numbers but if you just put in 12345.. it will complain.)

- `KEYCLOAK_REALM`

  Sets the realm used by APISIX for Keycloak authentication. Defaults to `ol-local`.

- `KEYCLOAK_DISCOVERY_URL`

  Sets the discovery URL for the Keycloak OIDC service. (In Keycloak admin, navigate to the realm you're using, then go to Realm Settings under Configure, and the link is under OpenID Endpoint Configuration.) This defaults to a valid value for the pack-in Keycloak instance.

- `KEYCLOAK_CLIENT_ID`

  The client ID for the OIDC client for APISIX. Defaults to `apisix`.

- `KEYCLOAK_CLIENT_SECRET`

  The client secret for the OIDC client. No default - you will need to get this from the Keycloak admin, even if you're using the pack-in Keycloak instance.

#### Other Settings

- **CyberSource**: You'll need to get CyberSource settings to make this app actually work. These can be pulled out of another _CI or RC_ app. _Do not_ pull these from a production app - the non-prod ones use test accounts that won't make real charges on the submitted card. See also the documentation in ol-django's payment_gateway app for info.
- **Google Sheets**: The app can pull refund request from Google Sheets. If you want this functionality to work, check out the documentation in ol-django for `google_sheets` and `google_sheets_refunds`. See also the section later about this.
  - If you want to set this up, you'll need to expose the app to the Internet. You may need to update your CORS, CSRF, and allowed hosts settings so your Internet-accessible domain is in the list.
- **Path prefix routing**: In the deployed instances, we route requests to the app using a path prefix. The app includes support for prepending a prefix to its routes if you want to do this without setting up rewrites in APISIX. Set `MITOL_APP_PATH_PREFIX` to enable this.

### Loading and Accessing Data

You'll need an integrated system and product for that system to be able to do much of anything. A management command exists to create the test data: `generate_test_data`. This will create a system and add some products with random (but usable) prices in it.

Alternatively, you can create them manually:

- Create an integrated system: `./manage.py add_system <name> -d <description> -s <slug`
- Create a product: `./manage.py manage_product add -s <system slug> --sku <an SKU> --name <name> --description <description> --price <price>`

The `add_system` command will generate an API key for the system's use. You can add as many systems as you wish.

> Alternatively, you can create these records through the Django Admin, but be advised that it won't create the API key for you. The management command uses a UUID for the key but any value will do, as long as it's unique.

### API Access

You can interact with the API directly through the Swagger interface: `<root url>/api/v0/schema/swagger-ui/`

The system also exposes a Redoc version of the API at `<root url>/api/v0/schema/redoc/`

Navigating to an API endpoint in the browser should also get you the normal DRF interface as well.

> [!NOTE]
> Most API endpoints require authentication, so you won't be able to get a lot of these to work without the API Gateway in place. The API documentation interfaces are accessible without authentication, though.

### Managing APISIX

If you have a need to adjust the APISIX settings (which would include routes), you can do so by modifying the configuration files in `config/apisix`.

APISIX checks these files for changes _every second_ - you're supposed to add `#END` to the end of the file to signify that the data has changed. You should see some log entries once it's found changes and reloaded the data.

The three files in here control different things:

| File          | Use                                                                                      |
| ------------- | ---------------------------------------------------------------------------------------- |
| `config.yaml` | APISIX service configuration - TCP ports, deployment settings, plugin loading, SSL, etc. |
| `apisix.yaml` | Data for the service - **routes**, **upstreams**, clients, plugin configs, etc.          |
| `debug.yaml`  | Debugging settings.                                                                      |

The two files most likely to need to change are `apisix.yaml`, which controls routing to the underlying service, and `debug.yaml`, which allows you to configure debug logging for APISIX and its plugins.

Use the documentation and the APISIX source code to determine what goes in each file.

Note that, since APISIX is run in "decoupled"/"standalone" mode, you _cannot_ use the API to control it. All changes and state introspection is done from the yaml files.

If you're getting 404 errors for all routes, make sure you've set the session key as noted above, and watch the logs for the `api` container. Debug mode is turned on so you should see errors on startup if it's unable to parse the routes file (`apisix.yaml`).

The configuration should be generic enough that it should work across the board. Don't commit changes to these files unless you really need to.

## Code Generation

Unified Ecommerce uses [drf-spectacular](https://drf-spectacular.readthedocs.io/en/latest/) to generate an OpenAPI spec from Django views. The generated spec is checked into source control; CI checks that it are up-to-date. To regenerate these files, run

```bash
./scripts/generate_openapi.sh
```

> The actual API client is built separately.

## Committing & Formatting

To ensure commits to GitHub are safe, first install [pre-commit](https://pre-commit.com/):

```
pip install pre_commit
pre-commit install
```

Running pre-commit can confirm your commit is safe to be pushed to GitHub and correctly formatted:

```
pre-commit run --all-files
```

To automatically install precommit hooks when cloning a repo, you can run this:

```
git config --global init.templateDir ~/.git-template
pre-commit init-templatedir ~/.git-template
```

## Optional Setup

Described below are some setup steps that are not strictly necessary for running Unified Ecommerce.

### Interstitial Debug Mode

You can set `MITOL_UE_PAYMENT_INTERSTITIAL_DEBUG` to control whether or not the checkout interstitial page displays additional data and waits to submit or not. By default, this tracks the `DEBUG` setting (so it should be off in production, and on in local testing).

### Google Sheets Processing

The system can process refund requests that come in through a Google Sheet (i.e., in the way that they do in MITx Online).

The setup for this is best described in the `ol-django` apps that are the backbone of this integration:

- `google_sheets`: https://github.com/mitodl/ol-django/blob/main/src/google_sheets/README.md
- `google_sheets_refunds`: https://github.com/mitodl/ol-django/blob/main/src/google_sheets_refunds/README.md

The _tl;dr_ is that you'll need to get a copy of the existing refunds sheet (or set one up yourself), get OAuth2 credentials established in Google to access the sheet, then run through the OAuth2 workflow so that the app can get to the sheet (which will require `ngrok` or similar).

### Webhook Retry

The events system will attempt to ping integrated systems via a webhook when orders hit certain states (such as completed or refunded). You can control how this works with these settings:

- `MITOL_UE_WEBHOOK_RETRY_MAX` - Max number of attempts to make to hit a webhook. Defaults to 4.
- `MITOL_UE_WEBHOOK_RETRY_COOLDOWN` - How long to wait between retrying, in seconds. Defaults to 60 seconds.

The retry happens if the request times out, returns an HTTP error, or returns a connection error. If the webhook isn't configured with a URL, if it returns non-JSON data or a redirect loop, or some other error happens, the system _will not_ retry the webhook and an error message will be emitted to that effect. Similarly, if it falls out the end of the available retries it will also emit an error message and stop.

### Running the app in a notebook

This repo includes a config for running a [Jupyter notebook](https://jupyter.org/) in a Docker container. This enables you to do in a Jupyter notebook anything you might otherwise do in a Django shell. To get started:

- Copy the example file
  ```bash
  # Choose any name for the resulting .ipynb file
  cp app.ipynb.example app.ipynb
  ```
- Build the `notebook` container _(for first time use, or when requirements change)_
  ```bash
  docker compose -f docker-compose-notebook.yml build
  ```
- Run all the standard containers (`docker compose up`)
- In another terminal window, run the `notebook` container
  ```bash
  docker compose -f docker-compose-notebook.yml run --rm --service-ports notebook
  ```
- The notebook container log output will indicate a URL at which you can interact with the notebook server.
- After visiting the notebook url, click the `.ipynb` file that you created to run the notebook
- Execute the first block to confirm it's working properly (click inside the block and press Shift+Enter)

From there, you should be able to run code snippets with a live Django app just like you would in a Django shell.

### Change ports

If you need, you can change the exposed ports for all services:

```
POSTGRES_PORT=5420
APISIX_PORT=9080
KEYCLOAK_SSL_PORT=7443
KEYCLOAK_PORT=7080
NGINX_PORT=8073
```

If you change these, you may need to update settings elsewhere. (Note that the APISIX config references `nginx:8073` but since it's _within_ the Docker network for the app, you don't need to update its port if you change it in your `.env` file.)

### Import MaxMind GeoIP data

The blocked country and tax assessment checks need the MaxMind GeoLite2 dataset to be imported into the app.

You'll need to retrieve a copy of the data. You can get this for free from MaxMind: https://dev.maxmind.com/ Use the blue "Sign up for a GeoLite2 account" at the bottom to sign up for an account, and then you can download the data. There are several versions of the data to download - generally the "Country: CSV Format" is the best option. (You _have_ to use a CSV option, however.)

Once you've downloaded it, place the CSV files in the root directory and then you can run this one-liner:

```
docker compose exec web ./manage.py import_maxmind_data GeoLite2-Country-Locations-en.csv geolite2-country-locations ; docker compose exec web ./manage.py import_maxmind_data GeoLite2-Country-Blocks-IPv4.csv geolite2-country-ipv4 ; docker compose exec web ./manage.py import_maxmind_data GeoLite2-Country-Blocks-IPv6.csv geolite2-country-ipv6
```

You can also (and probably should) add mappings for private IPs too. Private IPs aren't represented by default in the GeoIP databases. Run `docker compose exec web ./manage.py create_private_maxmind_data <ISO code>` to do this. The ISO code can be anything that's a valid ISO 3166 code (so, US works, but you can set it to something else if you'd prefer).
