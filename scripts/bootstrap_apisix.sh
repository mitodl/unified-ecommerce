#!/bin/bash

# Bootstraps a local APISIX instance.

# Uncomment and fill these in.
# APISIX_ROOT=<root location for APISIX - no trailing slash>
# API_KEY=<api key>
# OIDC_REALM=<your Keycloak realm>
# CLIENT_ID=<your client ID>
# CLIENT_SECRET=<your client secret>
# DISCOVERY_URL=<OpenID Endpoint Configuration link>

# Define upstream connection

curl "${APISIX_ROOT}/apisix/admin/upstreams/2" \
	-H "X-API-KEY: $API_KEY" -X PUT -d '
{
  "type": "roundrobin",
  "nodes": {
    "nginx:8073": 1
  }
}'

# Define the Universal Ecommerce wildcard route

postbody=$(
	cat <<ROUTE_END
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

curl "${APISIX_ROOT}/apisix/admin/routes/ue" -H "X-API-KEY: $API_KEY" -X PUT -d "${postbody}"
