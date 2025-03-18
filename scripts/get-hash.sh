#!/bin/sh

# Simple wrapper to get the current Git hash and store it in staticfiles/hash.txt.

set -e
git rev-parse HEAD >hash.txt
