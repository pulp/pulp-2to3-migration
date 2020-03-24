Configuration
=============

Requirements
------------

* /var/lib/pulp is shared from Pulp 2 machine
* access to Pulp 2 database


Configuration
-------------

On Pulp 2 machine
*****************

1. Make sure MongoDB listens on the IP address accesible outside, it should be configured as
one of the ``bindIP``s in ``/etc/mongod.conf``.

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
