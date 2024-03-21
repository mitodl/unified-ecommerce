# MIT OL Unified Ecommerce

This application provides a central system to handle ecommerce activities across the Open Learning web applications.

**SECTIONS**

- [MIT OL Unified Ecommerce](#mit-ol-unified-ecommerce)
  - [Initial Setup](#initial-setup)
    - [Configure required `.env` settings](#configure-required-env-settings)
    - [Loading and Accessing Data](#loading-and-accessing-data)
    - [Run with API Gateway](#run-with-api-gateway)
      - [Traefik](#traefik)
      - [Others (APISIX)](#others-apisix)
  - [Code Generation](#code-generation)
  - [Committing \& Formatting](#committing--formatting)
  - [Optional Setup](#optional-setup)
    - [Running the app in a notebook](#running-the-app-in-a-notebook)

## Initial Setup

Unified Ecommerce follows the same [initial setup steps outlined in the common OL web app guide](https://mitodl.github.io/handbook/how-to/common-web-app-guide.html).
Run through those steps **including the addition of `/etc/hosts` aliases and the optional step for running the
`createsuperuser` command**.

Additionally, you will need a Keycloak instance set up with a realm for the application. The realm can be an existing one (and should if you want to use the same accounts from another integrated app). The application needs a service account for the app (so it can pull user information) in the _master_ realm and a client.

### Configure required `.env` settings

The following settings must be configured before running the app:

- `MITOL_UE_HOSTNAME`

  Sets the hostname required by webpack for building the frontend. Should likely be whatever you set
  the host to in your /etc/hosts or the hostname that you're accessing it from. Likely `ue.odl.local`.

- `SECRET_KEY`

  Sets the Django secret for the application. This just needs to be a random string.

- `KEYCLOAK_ADMIN_CLIENT_ID`

  Sets the client ID for the service account. (This should be in the `master` realm.)

- `KEYCLOAK_ADMIN_CLIENT_SECRET`

  Sets the client secret for the service account.

- `KEYCLOAK_URL`

  Sets the base URL for the Keycloak instance. Do not append a trailing slash.

- `KEYCLOAK_REALM`

  Sets the realm name that the application should use.

If you're going to use the included Traefik Composer environment, also set these:

- `KEYCLOAK_CLIENT_ID`

  Sets the client ID for authentication within the realm.

- `KEYCLOAK_CLIENT_SECRET`

  Sets the client secret for authentication within the realm.

- `TRAEFIK_SECRET`

  Sets the secret Traefik will use for cookie generation (works like the Django `SECRET_KEY`).

### Loading and Accessing Data

You'll need an integrated system and product for that system to be able to do much of anything. Once you've done initial setup, run these commands:

* Create an integrated system: `./manage.py add_system <name> -d <description> -s <slug`
* Create a product: `./manage.py manage_product add -s <system slug> --sku <an SKU> --name <name> --description <description> --price <price>`

The `add_system` command will generate an API key for the system's use. You can add as many systems as you wish.

> Alternatively, you can create these records through the Django Admin, but be advised that it won't create the API key for you. The management command uses a UUID for the key but any value will do, as long as it's unique.

You can interact with the API directly through the Swagger interface: `<root url>/api/schema/swagger-ui/`

The system also exposes a Redoc version of the API at `<root url>/api/schema/redoc/`

Navigating to an API endpoint in the browser should also get you the normal DRF interface as well.

> Most API endpoints will require a session of some kind. See Run with API Gateway below for more info. But, the integrated systems and products APIs are anoymous read-only, so you should be able to get something out of them without having the API gateway set up.

### Run with API Gateway

The app depends on an outside system to provide the authentication layer for itself. This outside system is an API gateway. We've specifically tested two: Traefik Proxy and APISIX.

#### Traefik

The base `docker-compose.yml` has labels added to support running this with Traefik on your local machine. Traefik can run outside of the UE Compose environment - it wiill pick up the configuration it needs automatically. The Compose file expects the Traefik network to be named `traefik-keycloak_default`. You will need a ForwardAuth configured to forward authentication to your Keycloak instance for auth. (The app then uses `X-Forwarded-User` to figure out who the user is.)

If you don't have a Traefik instance set up, there's a `docker-compose-traefik.yml` file that you can use to set up a basic environment with a ForwardAuth that'll work for the app. Make sure the environment settings are set up properly (see above) and then bring the Compose environment up _in its own project_ - e.g., `docker-compose up -p traefik-keycloak -f docker-compose-traefik.yml`. If your project name is different, you'll have to change the base docker-compose file or create an override so that the `nginx` container sits in the right network.

#### Others (APISIX)

The system is also set up to run using APISIX as the gateway (to an extent). Use the `docker-compose-apisix.yml` file to spin up the application with APISIX and etcd. The APISIX configuration is not ready for production use - it's only here for assist in local testing and development.

You'll need to define routes for APISIX before it will handle traffic for the appplication. Here are the steps to accomplish that:

1. In your Keycloak instance, create a new Client in the realm you are going to use for UE.
   2. The `Client ID` can be any valid string - a good choice is `apisix-client`. Set this in your shell as `CLIENT_ID`.
   1. For local testing, it's OK to use `*` for both `Valid redirect URIs` and `Web origins`. This is not OK for anything attached to the Internet. 
   2. Make sure `Client authentication` is on, and `Standard flow` and `Implicit flow` are checked.
   3. After you've saved the client, go to Credentials and copy out the `Client secret`. (You may need to manually cut and paste; the copy to clipboard button has never worked for me.) Set this in your shell as `CLIENT_SECRET`. 
2. Set the realm you're using in your shell as `OIDC_REALM`.
3. In your Keycloak Realm Settings, you should be able to find the OpenID Endpoint Configuration link. Copy/paste this somewhere - you'll need it later. Set this in your shell as `DISCOVERY_URL`.
4. From the `config/apisix/apisix.yml` file, get the `key` out. This should be on line 11. You can also reset it here if you wish. Set this as `API_KEY`.
5. Start the entire thing: `docker compose -f docker-compose-apisix.yml up`. This will bring up Universal Ecommerce and the APISIX instance.
6. Create an all-encompassing route for UE in APISIX. This uses the APISIX API - be sure to read this through before running it and fill out placeholders.
```bash
# Set variables - skip if you were doing this in each step above

API_KEY=<api key>
OIDC_REALM=<your Keycloak realm>
CLIENT_ID=<your client ID>
CLIENT_SECRET=<your client secret>
DISCOVERY_URL=<OpenID Endpoint Configuration link>

# Define upstream connection

curl "http://127.0.0.1:9180/apisix/admin/upstreams/2" \
-H "X-API-KEY: $API_KEY" -X PUT -d '
{
  "type": "roundrobin",
  "nodes": {
    "nginx:8073": 1
  }
}'

# Define the Universal Ecommerce wildcard route

postbody=$(cat << ROUTE_END
{
  "uri": "/*",
  "plugins":{
    "openid-connect":{
      "client_id": "${CLIENT_ID}",
      "client_secret": "${CLIENT_SECRET}",
      "discovery": "${DISCOVERY_URL}",
      "scope": "openid profile",
      "bearer_only": false,
      "realm": "${OIDC_REALM}",
      "introspection_endpoint_auth_method": "client_secret_post"
    }
  },
  "upstream_id": 2
}
ROUTE_END
)

curl http://127.0.0.1:9180/apisix/admin/routes/ue -H "X-API-KEY: $API_KEY" -X PUT -d $postbody
```

You should now be able to get to the app via APISIX. There is an internal API at `http://ue.odl.local:9080/_/v0/meta/apisix_test_request/` that you can hit to see if it worked. The wildcard route above will route all UE traffic (or, more correctly, all traffic going into APISIX) through Keycloak and then into UE, so you should also be able to access the Django Admin through it if you've set your Keycloak user to be an admin.

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
