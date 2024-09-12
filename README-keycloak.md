# Keycloak Integration

The APISIX Compose file includes a Keycloak instance that you can use for authentication instead of spinning up a separate one or using one of the deployed instances. _By default, however, it doesn't work._ Some configuration is required, so by default this will start and then fail to configure itself and stop.

## Default Settings

There are some defaults that are part of this.

_SSL Certificate_: There's a self-signed cert that's in `config/keycloak/tls` - if you'd rather set up your own (or you have a real cert or something to use), you can drop the PEM files in there. See the README there for info.

_Realm_: There's a `default-realm.json` in `config/keycloak` that will get loaded by Keycloak when it starts up, and will set up a realm for you with some users and a client so you don't have to set it up yourself. The realm it creates is called `ol-local`.

The users it sets up are:

| User | Password |
|---|---|
| `student@odl.local` | `student` |
| `prof@odl.local` | `prof` |
| `admin@odl.local` | `admin` |

The client it sets up is called `apisix`. You can change the passwords and get the secret in the admin.

## Making it Work

If you want to use the Keycloak instance, follow these steps:

1. In `config/keycloak/tls`, copy `tls.crt.default` and `tls.key.default` to `tls.crt` and `tls.key`. (Or, you can regenerate them - see the README in that folder.)
2. Create a database called `keycloak`. For example: `docker compose -f docker-compose-apisix.yml run --rm -ti db psql -h db -U postgres -c 'create database keycloak;'` (then enter the default password of `postgres` when it asks)
3. Optionally add `KEYCLOAK_SVC_HOSTNAME`, `KEYCLOAK_SVC_ADMIN`, and `KEYCLOAK_SVC_ADMIN_PASSWORD` to your `.env` file.
   1. `KEYCLOAK_SVC_HOSTNAME` is the hostname you want to use for the instance - the default is `kc.odl.local`.
   2. `KEYCLOAK_SVC_ADMIN` is the admin username. The default is `admin`.
   3. `KEYCLOAK_SVC_ADMIN_PASSWORD` is the admin password. The default is `admin`.
4. Start the Keycloak service: `docker compose -f docker-compose-apisix.yml up -d keycloak`

The Keycloak container should start and stay running. Once it does, you should be able to log in at `https://kc.odl.local:7443/` with username and password `admin`. (Substitute your changes in there if you've made any.)

Once you've got it up and running, you can follow the normal steps in the main README to configure APISIX to use the Keycloak container. (The Keycloak container should set your configured hostname as an alias, so you should be able to use e.g. `kc.odl.local` when defining routes, etc.)
