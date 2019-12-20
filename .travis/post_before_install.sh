#!/usr/bin/env bash

set -mveuo pipefail

sed -i "s/'seeds': 'localhost:27017'/'seeds': '$(hostname):27017'/g" $TRAVIS_BUILD_DIR/pulp_2to3_migration/app/settings.py
sed -i "s/'username': ''/'username': 'travis'/g" $TRAVIS_BUILD_DIR/pulp_2to3_migration/app/settings.py
sed -i "s/'password': ''/'password': 'travis'/g" $TRAVIS_BUILD_DIR/pulp_2to3_migration/app/settings.py
