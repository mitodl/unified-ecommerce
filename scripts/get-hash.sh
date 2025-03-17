#!/bin/sh

# Simple wrapper to get the current Git hash and store it in staticfiles/hash.txt.

git rev-parse origin >hash.txt
