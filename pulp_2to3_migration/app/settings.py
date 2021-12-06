PULP2_MONGODB = {
    'name': 'pulp_database',
    'seeds': 'localhost:27017',
    'username': '',
    'password': '',
    'replica_set': '',
    'ssl': False,
    'ssl_keyfile': '',
    'ssl_certfile': '',
    'verify_ssl': True,
    'ca_path': '/etc/pki/tls/certs/ca-bundle.crt',
}

ALLOWED_CONTENT_CHECKSUMS = ['md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512']

CONTENT_PREMIGRATION_BATCH_SIZE = 1000

# Since each deb_component creates a large number of Pulp2to3Content we need a much lower batch size
# for this type, in order to avoid CursorNotFound errors!
DEB_COMPONENT_BATCH_SIZE = 50
