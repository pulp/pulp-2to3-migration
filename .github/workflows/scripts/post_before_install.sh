#!/usr/bin/env bash

set -mveuo pipefail

export MONGODB_IP=$(ip address show dev docker0 | grep -o "inet [0-9]*\.[0-9]*\.[0-9]*\.[0-9]*" | grep -o "[0-9]*\.[0-9]*\.[0-9]*\.[0-9]*")
sed -i "s/'seeds': 'localhost:27017'/'seeds': '$MONGODB_IP:27017'/g" $GITHUB_WORKSPACE/pulp_2to3_migration/app/settings.py
sed -i "s/'username': ''/'username': 'ci_cd'/g" $GITHUB_WORKSPACE/pulp_2to3_migration/app/settings.py
sed -i "s/'password': ''/'password': 'ci_cd'/g" $GITHUB_WORKSPACE/pulp_2to3_migration/app/settings.py
cat $GITHUB_WORKSPACE/pulp_2to3_migration/app/settings.py >> $GITHUB_WORKSPACE/.ci/ansible/settings.py.j2
