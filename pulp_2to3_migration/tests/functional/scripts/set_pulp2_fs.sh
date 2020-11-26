#!/usr/bin/env bash

ARCHIVE_NAME=$1

[ ! -d "pulp-2to3-migration-test-fixtures" ] && git clone https://github.com/pulp/pulp-2to3-migration-test-fixtures
mv pulp-2to3-migration-test-fixtures/${ARCHIVE_NAME}/var/lib/pulp/content /var/lib/pulp/content
mv pulp-2to3-migration-test-fixtures/${ARCHIVE_NAME}/var/lib/pulp/published /var/lib/pulp/published