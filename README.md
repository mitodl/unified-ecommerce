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
    - [Running the app in a notebook](#running-the-app-in-a-notebook)

## Initial Setup

Unified Ecommerce follows the same [initial setup steps outlined in the common OL web app guide](https://mitodl.github.io/handbook/how-to/common-web-app-guide.html).
Run through those steps **including the addition of `/etc/hosts` aliases and the optional step for running the
`createsuperuser` command**.

Additionally, you will need a Keycloak instance set up with a realm for the application. The realm can be an existing one - if you have a realm set up for other applications (e.g. Learn), you should use that realm.

If you don't have a Keycloak instance set up, or if you want to test with a known-good configuration, the app can optionally run with its own Keycloak instance. See [README-keycloak.md](README-keycloak.md) for instructions.

### Configure required `.env` settings

The following settings must be configured before running the app:

- `MITOL_UE_HOSTNAME`

  Sets the hostname required by webpack for building the frontend. Should likely be whatever you set
  the host to in your /etc/hosts or the hostname that you're accessing it from. Likely `ue.odl.local`.

- `SECRET_KEY`

  Sets the Django secret for the application. This just needs to be a random string.

- `KEYCLOAK_REALM`

  Sets the realm used by APISIX for Keycloak authentication. Defaults to `ol-local`.

- `KEYCLOAK_DISCOVERY_URL`

  Sets the discovery URL for the Keycloak OIDC service. (In Keycloak admin, navigate to the realm you're using, then go to Realm Settings under Configure, and the link is under OpenID Endpoint Configuration.) This defaults to a valid value for the pack-in Keycloak instance.

- `KEYCLOAK_CLIENT_ID`

  The client ID for the OIDC client for APISIX. Defaults to `apisix`.

- `KEYCLOAK_CLIENT_SECRET`

  The client secret for the OIDC client. No default - you will need to get this from the Keycloak admin, even if you're using the pack-in Keycloak instance.

### Loading and Accessing Data

You'll need an integrated system and product for that system to be able to do much of anything. A management command exists to create the test data: `generate_test_data`. This will create a system and add some products with random (but usable) prices in it.

Alternatively, you can create them manually:

* Create an integrated system: `./manage.py add_system <name> -d <description> -s <slug`
* Create a product: `./manage.py manage_product add -s <system slug> --sku <an SKU> --name <name> --description <description> --price <price>`

The `add_system` command will generate an API key for the system's use. You can add as many systems as you wish.

> Alternatively, you can create these records through the Django Admin, but be advised that it won't create the API key for you. The management command uses a UUID for the key but any value will do, as long as it's unique.

### API Access

You can interact with the API directly through the Swagger interface: `<root url>/api/schema/swagger-ui/`

The system also exposes a Redoc version of the API at `<root url>/api/schema/redoc/`

Navigating to an API endpoint in the browser should also get you the normal DRF interface as well.

> [!NOTE]
> Most API endpoints require authentication, so you won't be able to get a lot of these to work without the API Gateway in place. The API documentation interfaces are accessible without authentication, though.

### Managing APISIX

If you have a need to adjust the APISIX settings (which would include routes), you can do so by modifying the configuration files in `config/apisix`.

APISIX checks these files for changes _every second_ - you're supposed to add `#END` to the end of the file to signify that the data has changed. You should see some log entries once it's found changes and reloaded the data.

The three files in here control different things:

| File | Use |
|---|---|
| `config.yaml` | APISIX service configuration - TCP ports, deployment settings, plugin loading, SSL, etc. |
| `apisix.yaml` | Data for the service - **routes**, **upstreams**, clients, plugin configs, etc. |
| `debug.yaml` | Debugging settings. |

The two files most likely to need to change are `apisix.yaml`, which controls routing to the underlying service, and `debug.yaml`, which allows you to configure debug logging for APISIX and its plugins.

Use the documentation and the APISIX source code to determine what goes in each file.

Note that, since APISIX is run in "decoupled"/"standalone" mode, you _cannot_ use the API to control it. All changes and state introspection is done from the yaml files.

## Code Generation

Unified Ecommerce uses [drf-spectacular](https://drf-spectacular.readthedocs.io/en/latest/) to generate an OpenAPI spec from Django views. Additionally, we use [OpenAPITools/openapi-generator](https://github.com/OpenAPITools/openapi-generator) to generate Typescript declarations and an API Client. These generated files are checked into source control; CI checks that they are up-to-date. To regenerate these files, run

```bash
./scripts/generate_openapi.sh
```

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
