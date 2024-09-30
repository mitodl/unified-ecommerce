#!/bin/bash

# Bootstraps a local APISIX instance.

# Uncomment and fill these in.
APISIX_ROOT=http://kc.odl.local:9180
API_KEY=edd1c9f034335f136f87ad84b625c8f1
OIDC_REALM=ol-local
CLIENT_ID=apisix
CLIENT_SECRET=HckCZXToXfaetbBx0Fo3xbjnC468oMi4
DISCOVERY_URL=http://kc.odl.local:7080/realms/ol-local/.well-known/openid-configuration

# Define upstream connection

curl "${APISIX_ROOT}/apisix/admin/upstreams/2" \
	-H "X-API-KEY: $API_KEY" -X PUT -d '
{
  "type": "roundrobin",
  "nodes": {
    "nginx:8073": 1
  }
}'

# Define the Universal Ecommerce unauthenticated route
# This is stuff that doesn't need a session - static resources, and the checkout result API

postbody=$(
	cat <<ROUTE_END
{
  "uris": [ "/checkout/result/", "/static", "/api/schema" ],
  "plugins": {},
  "upstream_id": 2,
  "priority": 0,
  "desc": "Unauthenticated routes, including assets and the checkout callback API",
  "name": "ue-unauth"
}
ROUTE_END
)

curl http://127.0.0.1:9180/apisix/admin/routes/ue-unauth -H "X-API-KEY: $API_KEY" -X PUT -d "$postbody"

# Define the Universal Ecommerce wildcard route

postbody=$(
	cat <<ROUTE_END
{
  "name": "ue-default",
  "desc": "Wildcard route for the rest of the system - authentication required",
  "priority": 1,
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

curl "${APISIX_ROOT}/apisix/admin/routes/ue-default" -H "X-API-KEY: $API_KEY" -X PUT -d "${postbody}"
