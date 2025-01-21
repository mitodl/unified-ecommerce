#!/usr/bin/env bash
set -eo pipefail

TMPDIR="$(mktemp -p . -d)"
SPECS_DIR=./openapi/specs/

docker compose run --rm web ./manage.py generate_openapi_spec \
	--directory=$TMPDIR --fail-on-warn

npx run prettier --write $TMPDIR

diff $TMPDIR $SPECS_DIR

if [ $? -eq 0 ]; then
	echo "OpenAPI spec is up to date!"
	exit 0
else
	echo "OpenAPI spec is out of date. Please regenerate via ./scripts/generate_openapi.sh"
	exit 1
fi
