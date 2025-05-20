# API Gateway Integration

The Unified Ecommerce application expects to be run behind the APISIX API gateway. APISIX's main job is to coordinate the integration between the application and SSO.

## Reasoning

The Unified Ecommerce application doesn't have (or need) its own login UI. It's intended to be used in conjunction with other systems, so it needs to share authentication and accounts with those systems. In addition, these accounts all need to be in sync with each other.

We've chosen Keycloak as the authentication system for Open Learning applications. It is the source of truth for user information and authentication, and other Open Learning applications are configured to use it for authentication. They redirect the user to Keycloak, and then Keycloak verifies the user and sends them back to the application (via OAuth2/OIDC).

For UE, APISIX handles this integration with Keycloak. For certain API endpoints, APISIX itself checks for a session and redirects the user through Keycloak. It then passes the user on to UE and attaches a payload of the user data in the headers. UE can then set up the Django session, create or update the local user account, and check permissions as it needs.

UE doesn't have to coordinate with Keycloak or use OIDC at all in this scenario. APISIX controls that. Additionally, the APISIX configuration can be shared across services, so ideally everything routes through it, and users can seamlessly transition between individual applications after authenticating once.

## Authentication Workflow

Unified Ecommerce API endpoints generally fall into one of three categories:

- Anonymous access: a number of APIs are accessible anonymously. (Product information falls into this category.)
- Authenticated access: other APIs require a session to be established within Unified Ecommerce. (Basket and order information APIs are in this category.)
- Transitional access: specific APIs that handle transition between anonymous and authenticated access. (Essentially, login.)

For anonymous access APIs, APISIX is configured to pass these along without change or processing. Any existing Django session will be used.

For authenticated access APIs, APISIX is configured in the same way, and passes these along as well. The user will receive an error if the Django session isn't established beforehand.

Transitional access APIs involve the APISIX OIDC integration.

```{mermaid}
---
title: Session Establishment
---
flowchart LR
    accessEndpoint["User hits the endpoint"]
    hasApisixSession["User has an APISIX session"]
    redirectSso["Redirected to Keycloak SSO"]
    ssoAuth["Log in via SSO"]
    ssoAuthOk["SSO Auth OK"]
    ssoAuthBad["SSO Auth Fail"]
    apisixAuth["Session setup in APISIX"]
    intoDjango["Redirect into Django"]
    fail["Auth failed"]

    accessEndpoint --> hasApisixSession
    hasApisixSession --> intoDjango
    hasApisixSession --> redirectSso
    redirectSso --> ssoAuth
    ssoAuth --> ssoAuthBad
    ssoAuth --> ssoAuthOk
    ssoAuthOk --> apisixAuth
    ssoAuthBad --> fail
    apisixAuth --> intoDjango
```

Since APISIX sits before the Django app, it will first check to see if the user has a session established in APISIX. If it does, then the user is passed along to the Django app. If not, the user is redirected into Keycloak to log in. Assuming that succeeds, APISIX receives the user back, sets up its own session, and then sends the user to the Django app with the APISIX payload attached. (If the user can't get past Keycloak, the process stops.)

APISIX attaches user information in a special `X-UserInfo` header. A middleware within the Django app processes this header, either updates or creates a user account, and establishes a Django session for the account with the data contained within.

This workflow is used by the `/establish_session` endpoint. The frontend calls an endpoint to retrieve the current user data, and redirects the user to `/establish_session` if the user's not logged in. This endpoint then logs the user in with the processed APISIX data, starts a Django session, and sends the user back to the frontend. The user can then use the rest of the API as an authenticated user.

## X-UserInfo

When configured to use authentication via OIDC Connect, APISIX returns the user data back to the application by injecting it into the HTTP headers sent to the app. A custom middleware in the application decodes this data, and takes action based on it.

APISIX sends user data retrieved via OIDC in the `X-UserInfo` header. The data is sent as a base64-encoded JSON object, and its contents may vary but include:

- The user's email address (`email`)
- The UUID associated with the user in the SSO system (`preferred_username`)
- The user's first and last name (`given_name`, `family_name`)

The middleware creates or updates the user account based on this data and sets the session user appropriately.

```{note}
Regular forward authentication doesn't include the user data. If we used that, the app would have to perform a round-trip to Keycloak to retrieve it.
```

### Trust

Having the app configured in this way means that it **must** sit behind APISIX. At time of writing, the APISIX middleware also blindly trusts the payload that APISIX sends along. So, the Django app must not be exposed directly to the Internet when it is deployed.
