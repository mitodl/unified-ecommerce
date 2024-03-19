# API Gateway Integration

The Unified Ecommerce application expects to be run behind an API gateway of some sort to provide authentication support. The application supports two protocols for this:

- Forward Authentication: the API gateway provides only username of the authenticated user to the application
- X-UserInfo: the API gateway provides a more complete user record to the application

Of these, the latter is the preferred method as it doesn't entail a further API call to another service to retrieve the user data.

## Forward Authentication

Forward auth is provided by a number of API gateway (and gateway-like) services, including Traefik. To support this, the app extends the built-in Django `RemoteUserMiddleware` to use the  `X-Forwarded-User` header. In addition to this, the app then attempts to load the user data from Keycloak to fill out the user account, as the only data that will be passed along will be the username.

The app requires a service account in the relevant Keycloak realm so that it can pull user data. 

## X-UserInfo

This method is useful when a more fully-fledged API gateway system is placed in front of the app. (APISIX is the canonical example and was the service that was used to write the initial integration, so this info is geared towards using APISIX.) 

### Method of Operation

When configured to use authentication via OIDC Connect, APISIX returns the user data back to the application by injecting it into the HTTP headers sent to the app. A custom middleware in the application decodes this data, and takes action based on it. 

For _local_ deployments, APISIX sends user data retrieved via OIDC in the `X-UserInfo` header. The data is sent as a base64-encoded JSON object, and its contents may vary but include:
- The user's email address (`email`)
- The UUID associated with the user in the SSO system (`preferred_username`)
- The user's first and last name (`given_name`, `family_name`)

The middleware creates or updates the user account based on this data and sets the session user appropriately. Note that, unlike forward authentication, APISIX includes enough user data to construct and update the user record so the app does not need to make a separate call to Keycloak directly for this data.

For Heroku deployments, we do something different because we need to be able to trust the data in the `X-UserInfo` header. _TODO:_ Fill this out - we don't have the info here yet.
