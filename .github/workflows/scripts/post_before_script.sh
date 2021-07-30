#!/usr/bin/env bash

set -euv

export MONGODB_IP=$(ip address show dev docker0 | grep -o "inet [0-9]*\.[0-9]*\.[0-9]*\.[0-9]*" | grep -o "[0-9]*\.[0-9]*\.[0-9]*\.[0-9]*")

sudo sed -i  "s/bindIp: 127.0.0.1/bindIp: 127.0.0.1,$MONGODB_IP/g" /etc/mongod.conf
sudo systemctl restart mongod

# update settings to configure our mongo install
cmd_prefix bash -c "cat >> /etc/pulp/settings.py <<EOF
PULP2_MONGODB = {
  'name': 'pulp_database',
  'seeds': '$MONGODB_IP:27017',
  'username': 'ci_cd',
  'password': 'ci_cd',
  'replica_set': '',
  'ssl': False,
  'ssl_keyfile': '',
  'ssl_certfile': '',
  'verify_ssl': True,
  'ca_path': '/etc/pki/tls/certs/ca-bundle.crt',
}
EOF"

# Restarting single container services
cmd_prefix bash -c "s6-svc -r /var/run/s6/services/pulpcore-api"
cmd_prefix bash -c "s6-svc -r /var/run/s6/services/pulpcore-content"
cmd_prefix bash -c "s6-svc -r /var/run/s6/services/pulpcore-resource-manager"
cmd_prefix bash -c "s6-svc -r /var/run/s6/services/pulpcore-worker@1"
cmd_prefix bash -c "s6-svc -r /var/run/s6/services/pulpcore-worker@2"

# install mongo and copy a script which we need to use for func tests to roll out a pulp 2 snapshot
cmd_prefix bash -c "cat > /etc/yum.repos.d/mongodb-org-3.6.repo <<EOF
[mongodb-org-3.6]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/8Server/mongodb-org/3.6/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://www.mongodb.org/static/pgp/server-3.6.asc
EOF"

cmd_prefix bash -c "dnf install -y mongodb-org-tools mongodb-org-shell"
cat pulp_2to3_migration/tests/functional/scripts/set_pulp2.sh | cmd_stdin_prefix bash -c "cat > /tmp/set_pulp2.sh"
cmd_prefix bash -c "chmod 755 /tmp/set_pulp2.sh"
