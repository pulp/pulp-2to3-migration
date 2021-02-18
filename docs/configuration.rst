Configuration
=============

Requirements
------------

* ``/var/lib/pulp`` is shared from Pulp 2 machine
* access to Pulp 2 database
* [recommended] all Pulp 3 supported checksum types are allowed


Configuration
-------------

On Pulp 2 machine
*****************

1. Make sure MongoDB listens on the IP address accesible outside, it should be configured as
one of the ``bindIP`` in ``/etc/mongod.conf``.

2. Make sure ``/var/lib/pulp`` is on a shared filesystem.


On Pulp 3 machine
*****************

1. Mount ``/var/lib/pulp`` to your Pulp 3 storage location. By default, it's ``/var/lib/pulp``.

2. Configure your connection to MongoDB in your settings, ``/etc/pulp/settings.py``. You can use
the same configuration as you have in Pulp 2 (only seeds might need to be different, it depends
on your setup). By default it's configured to connect to ``localhost:27017``.

E.g.

.. code:: python

    PULP2_MONGODB = {
        'name': 'pulp_database',
        'seeds': '<your MongoDB bindIP>:27017',
        'username': '',
        'password': '',
        'replica_set': '',
        'ssl': False,
        'ssl_keyfile': '',
        'ssl_certfile': '',
        'verify_ssl': True,
        'ca_path': '/etc/pki/tls/certs/ca-bundle.crt',
    }

3. Configure `ALLOWED_CONTENT_CHECKSUMS` in your settings, ``/etc/pulp/settings.py`` before you
run a migration. It is recommended to list all Pulp 3 supported checksum types.
pulp-2to3-migration is shipped with such default configuration. In case you have a custom one in
``/etc/pulp/settings.py``, make sure it lists all types as shown below:

.. code:: python

    ALLOWED_CONTENT_CHECKSUMS = ['md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512']

If you are sure that your Pulp 2 installation has no md5 or sha1 checksums for any content
(on_demand or downloaded) or in any distributor configuration, then you are fine to exclude those
from the setting.

If you are concerned having `md5` and `sha1` enabled, you can always adjust the setting after
the migration is done and remove those two checksum types from the allowed list. After modifying
the setting, you likely will need to run ``pulpcore-manager handle-artifact-checksums`` to remove
unsupported checksums from the database, or Pulp will refuse to start.