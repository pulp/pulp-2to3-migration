#!/usr/bin/env bash

set -euv

$CMD_PREFIX bash -c "git clone https://github.com/pulp/pulp-2to3-migration-test-fixtures"
$CMD_PREFIX bash -c "mv pulp-2to3-migration-test-fixtures/20191031/var/lib/pulp/content /var/lib/pulp/content"
$CMD_PREFIX bash -c "mv pulp-2to3-migration-test-fixtures/20191031/var/lib/pulp/published /var/lib/pulp/published"

wget https://github.com/pulp/pulp-2to3-migration-test-fixtures/raw/master/20191031/pulp2filecontent.20191031.archive
mongorestore --archive=pulp2filecontent.20191031.archive