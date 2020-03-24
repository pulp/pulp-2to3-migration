User Setup
==========

Ansible Installer (Recommended)
-------------------------------

We recommend that you install `pulpcore`, all the content plugins you need and
`pulp-2to3-migration` plugin together using the `Ansible installer
<https://github.com/pulp/ansible-pulp/blob/master/README.md>`_. The remaining steps are all
performed by the installer and are not needed if you use it.

Pip Install
-----------

This document assumes that you have
`installed pulpcore <https://docs.pulpproject.org/en/3.0/nightly/installation/instructions.html>`_
and any content plugins you need into the virtual environment ``pulpvenv``.

Users should install from **either** PyPI or source.

From PyPI
*********

.. code-block:: bash

   sudo -u pulp -i
   source ~/pulpvenv/bin/activate
   pip install pulp-2to3-migration

From Source
***********

.. code-block:: bash

   sudo -u pulp -i
   source ~/pulpvenv/bin/activate
   git clone https://github.com/pulp/pulp-2to3-migration.git
   cd pulp-2to3-migration
   pip install -e .

Make and Run Migrations
-----------------------

.. code-block:: bash

   export DJANGO_SETTINGS_MODULE=pulpcore.app.settings
   django-admin makemigrations pulp_2to3_migration
   django-admin migrate pulp_2to3_migration

Run Services
------------

.. code-block:: bash

   django-admin runserver 24817
   gunicorn pulpcore.content:server --bind 'localhost:24816' --worker-class 'aiohttp.GunicornWebWorker' -w 2
   sudo systemctl restart pulpcore-resource-manager
   sudo systemctl restart pulpcore-worker@1
   sudo systemctl restart pulpcore-worker@2
