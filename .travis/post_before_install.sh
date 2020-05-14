#!/usr/bin/env bash

set -mveuo pipefail

export MONGODB_IP=$(ip address show dev docker0 | grep -o "inet [0-9]*\.[0-9]*\.[0-9]*\.[0-9]*" | grep -o "[0-9]*\.[0-9]*\.[0-9]*\.[0-9]*")
sed -i "s/'seeds': 'localhost:27017'/'seeds': '$MONGODB_IP:27017'/g" $TRAVIS_BUILD_DIR/pulp_2to3_migration/app/settings.py
sed -i "s/'username': ''/'username': 'travis'/g" $TRAVIS_BUILD_DIR/pulp_2to3_migration/app/settings.py
sed -i "s/'password': ''/'password': 'travis'/g" $TRAVIS_BUILD_DIR/pulp_2to3_migration/app/settings.py
