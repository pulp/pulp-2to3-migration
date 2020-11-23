#!/usr/bin/env bash

set -euv

sudo sed -i  "s/bindIp: 127.0.0.1/bindIp: 127.0.0.1,$(ip address show dev docker0 | grep -o "inet [0-9]*\.[0-9]*\.[0-9]*\.[0-9]*" | grep -o "[0-9]*\.[0-9]*\.[0-9]*\.[0-9]*")/g" /etc/mongod.conf
sudo systemctl restart mongod

cmd_prefix bash -c "cat > /etc/yum.repos.d/mongodb-org-3.6.repo <<EOF
[mongodb-org-3.6]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/8Server/mongodb-org/3.6/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://www.mongodb.org/static/pgp/server-3.6.asc
EOF"

cmd_prefix bash -c "dnf install -y mongodb-org-tools mongodb-org-shell"

#cmd_prefix bash -c "git clone https://github.com/pulp/pulp-2to3-migration-test-fixtures"
#cmd_prefix bash -c "mv pulp-2to3-migration-test-fixtures/20191031/var/lib/pulp/content /var/lib/pulp/content"
#cmd_prefix bash -c "mv pulp-2to3-migration-test-fixtures/20191031/var/lib/pulp/published /var/lib/pulp/published"

#wget https://github.com/pulp/pulp-2to3-migration-test-fixtures/raw/master/20191031/pulp2filecontent.20191031.archive
#mongorestore --archive=pulp2filecontent.20191031.archive

#mongo pulp_database --eval 'db.createUser({user:"ci_cd",pwd:"ci_cd",roles:["readWrite"]});'

