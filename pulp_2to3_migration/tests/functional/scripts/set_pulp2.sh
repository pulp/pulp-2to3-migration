#!/usr/bin/env bash

MONGO_HOST=$1
ARCHIVE_NAME=$2

[ ! -d "pulp-2to3-migration-test-fixtures" ] && git clone https://github.com/pulp/pulp-2to3-migration-test-fixtures
sudo rm -rf /var/lib/pulp/content
sudo rm -rf /var/lib/pulp/published
cp -r pulp-2to3-migration-test-fixtures/${ARCHIVE_NAME}/var/lib/pulp/content /var/lib/pulp/
cp -r pulp-2to3-migration-test-fixtures/${ARCHIVE_NAME}/var/lib/pulp/published /var/lib/pulp/

mongo --host ${MONGO_HOST} pulp_database --eval 'db.dropDatabase();'
mongorestore --host ${MONGO_HOST} --archive=pulp-2to3-migration-test-fixtures/${ARCHIVE_NAME}/mongodb.${ARCHIVE_NAME}.archive --drop