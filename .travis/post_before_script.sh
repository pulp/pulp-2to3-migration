#!/usr/bin/env bash

set -euv

sudo sed -i  "s/bindIp: 127.0.0.1/bindIp: 127.0.0.1,$(ip address show dev ens4 | grep -o "inet [0-9]*\.[0-9]*\.[0-9]*\.[0-9]*" | grep -o "[0-9]*\.[0-9]*\.[0-9]*\.[0-9]*")/g" /etc/mongod.conf
sudo systemctl restart mongod

$CMD_PREFIX bash -c "git clone https://github.com/pulp/pulp-2to3-migration-test-fixtures"
$CMD_PREFIX bash -c "mv pulp-2to3-migration-test-fixtures/20191031/var/lib/pulp/content /var/lib/pulp/content"
$CMD_PREFIX bash -c "mv pulp-2to3-migration-test-fixtures/20191031/var/lib/pulp/published /var/lib/pulp/published"

wget https://github.com/pulp/pulp-2to3-migration-test-fixtures/raw/master/20191031/pulp2filecontent.20191031.archive
mongorestore --archive=pulp2filecontent.20191031.archive

mongo pulp_database --eval 'db.createUser({user:"travis",pwd:"travis",roles:["readWrite"]});'

cd ..
git clone https://github.com/pulp/pulp-openapi-generator.git
cd pulp-openapi-generator

./generate.sh pulpcore python
pip install ./pulpcore-client
./generate.sh pulp_file python
pip install ./pulp_file-client
./generate.sh pulp_2to3_migration python
pip install ./pulp_2to3_migration-client

