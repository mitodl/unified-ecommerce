# Keycloak Integration

The Compose file includes a Keycloak instance that you can use for authentication instead of spinning up a separate one or using one of the deployed instances. It's not enabled by default, but you can run it if you prefer not to run your own Keycloak instance.

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

The Keycloak instance is hidden in the `keycloak` profile in the Composer file, so if you want to interact with it, you'll need to run `docker compose --profile keycloak`. (If you start the app without the profile, you can still start Keycloak later by specifying the profile.)

If you want to use the Keycloak instance, follow these steps:

1. Start the stack normally. The `db` container needs to be up and running, at least.
1. In `config/keycloak/tls`, copy `tls.crt.default` and `tls.key.default` to `tls.crt` and `tls.key`. (Or, you can regenerate them - see the README in that folder.)
2. Create a database called `keycloak`. For example: `docker compose --profile keycloak run --rm -ti db psql -h db -U postgres -c 'create database keycloak;'` (then enter the default password of `postgres` when it asks)
3. Add a keystore password to your `.env` file. This should be set in `KEYCLOAK_SVC_KEYSTORE_PASSWORD`. This is required, but the password need not be anything special.
4. Optionally add `KEYCLOAK_SVC_HOSTNAME`, `KEYCLOAK_SVC_ADMIN`, and `KEYCLOAK_SVC_ADMIN_PASSWORD` to your `.env` file.
   1. `KEYCLOAK_SVC_HOSTNAME` is the hostname you want to use for the instance - the default is `kc.odl.local`.
   2. `KEYCLOAK_SVC_ADMIN` is the admin username. The default is `admin`.
   3. `KEYCLOAK_SVC_ADMIN_PASSWORD` is the admin password. The default is `admin`.
5. Start the Keycloak service: `docker compose --profile keycloak up -d keycloak`

The Keycloak container should start and stay running. Once it does, you should be able to log in at `https://kc.odl.local:7443/` with username and password `admin` (or the values you supplied).

Once you've got it up and running, you can follow the normal steps in the main README to configure APISIX to use the Keycloak container. Use the configured hostname (default `kc.odl.local`) where you need to use a hostname. (The Compose file configures it as an alias for the APISIX service, so it should work.)
