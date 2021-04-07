Configuration
=============

Requirements
------------

* ``/var/lib/pulp`` is shared from Pulp 2 machine
* access to Pulp 2 database
* [recommended] all Pulp 3 supported checksum types are allowed

.. note::

    The migration workload is very I/O intensive. It's highly recommended that the volume
    backing your Postgresql database be on a SSD or other low latency, high IOPS storage volume.


Configuration
-------------

On Pulp 2 machine
*****************

1. Make sure MongoDB listens on the IP address accesible outside, it should be configured as
one of the ``bindIP`` in ``/etc/mongod.conf``.

2. Make sure ``/var/lib/pulp`` is on a shared filesystem.

.. note::

    If you experience Pulp 2 workers timing out during the migration, consider making them more
    tolerant to delayed mongodb writes by increasing the ``worker_timeout`` setting in the
    ``[tasks]`` section of your Pulp 2 ``server.conf``. Typically a value of 300 seconds has worked
    well even during large migration workloads.


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

4. Configure `CONTENT_PREMIGRATION_BATCH_SIZE` if needed.
If your Pulp 2 setup is large and your system is relatively slow in terms of I/O (e.g. you have
HDD), consider adjusting the batch size for content premigration. The default is 1000.

It is recommended to decrease it gradually, approximately by half each time. On a very slow
system and with many errata content to migrate, it might need to go as low as 50. Decreasing the
value increases the time of content migration from pulp 2 to pulp 3. It's noticeable for a large
setups only.

The main sign that `CONTENT_PREMIGRATION_BATCH_SIZE` needs to go down is the ``pymongo.errors.CursorNotFound: Cursor not found`` errors in logs.

.. note::

    If you experience Pulp 3 workers timing out during the migration, consider making them more
    tolerant to delayed PostgreSQL writes by increasing the Pulp 3 ``WORKER_TTL`` setting. Typically
    a value of 300 seconds has worked well even during large migration workloads. This setting is
    available in ``pulpcore>=3.11``.
