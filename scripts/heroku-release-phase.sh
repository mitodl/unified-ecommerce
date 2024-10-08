#!/usr/bin/env bash

set -eo pipefail
indent() {
	RE="s/^/       /"
	[ "$(uname)" == "Darwin" ] && sed -l "$RE" || sed -u "$RE"
}

MANAGE_FILE=$(find . -maxdepth 3 -type f -name 'manage.py' | head -1)
# trim "./" from the path
MANAGE_FILE=${MANAGE_FILE:2}

# Run migrations

echo "-----> Running django migrations"
python $MANAGE_FILE showmigrations --list 2>&1 | indent
python $MANAGE_FILE migrate --noinput 2>&1 | indent

# Retaining this script in the should we require future post release actions
# we will have a recipe set to go.
echo "----> NOOP"
