#!/usr/bin/env bash
#
# This script runs the django app, waiting on the react applications to build

python3 manage.py collectstatic --noinput --clear
python3 manage.py migrate --noinput
python3 manage.py createcachetable

uwsgi uwsgi.ini --honour-stdin
