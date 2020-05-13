Workflows
=========

Run a migration task
--------------------

A recommended scenario:
 1. Pulp 2 is running, Pulp 3 is running (but the plugins which need to be migrated are not used, they don't have any data in Pulp 3).
 2. Run migration as many times as you need. No need to shut down Pulp 2. For large setups content migration can take a long time. Serve your clients from Pulp 2.
 3. When you are ready to switch to Pulp 3: run migration, then stop Pulp 2 services (so no new data is coming in), run migration for the last time (it should not take long).
 4. Serve your clients from Pulp3.

All the commands should be run on Pulp 3 machine.

1. Create a :doc:`Migration Plan <../migration_plan>`

.. code:: bash

    $ # migrate content for Pulp 2 ISO plugin
    $ http POST :24817/pulp/api/v3/migration-plans/ plan='{"plugins": [{"type": "iso"}]}'

    HTTP/1.1 201 Created
    {
        "pulp_created": "2019-07-23T08:18:12.927007Z",
        "pulp_href": "/pulp/api/v3/migration-plans/59f8a786-c7d7-4e2b-ad07-701479d403c5/",
        "plan": "{ "plugins": [{"type": "iso"}]}"
    }


2. Use the ``pulp_href`` of the created Migration Plan and its ``run/`` endpoint to run the
migration. Optionally, skip corrupted or missing Pulp 2 content by specifying the
``skip_corrupted=True`` parameter. For more details on migration options, check the `REST API docs <../restapi.html#operation/migration_plans_run>`_.

.. code:: bash

    $ http POST :24817/pulp/api/v3/migration-plans/59f8a786-c7d7-4e2b-ad07-701479d403c5/run/

    HTTP/1.1 202 Accepted
    {
        "task": "/pulp/api/v3/tasks/55db2086-cf2e-438f-b5b7-cd0dbb7c8cf4/"
    }

.. note::
    It is possible to re-run migration as many times as needed (if the Pulp 3 plugin which is
    being migrated is not used).


3. List the mapping for Pulp 2 and Pulp 3 repositories if needed.

.. code:: bash

    $ http :24817/pulp/api/v3/pulp2repositories/

    HTTP/1.1 200 OK
    {
        "count": 1,
        "next": null,
        "previous": null,
        "results": [
            {
                "is_migrated": true,
                "not_in_plan": false,
                "pulp2_object_id": "5dbc478c472f68283ad8e6bd",
                "pulp2_repo_id": "file-large",
                "pulp3_distribution_hrefs": [],
                "pulp3_publication_href": [],
                "pulp3_remote_href": "/pulp/api/v3/remotes/file/file/ca0e505e-51c2-46e1-be40-3762d372f9b2/",
                "pulp3_repository_version": null,
                "pulp_created": "2019-11-01T14:59:04.648920Z",
                "pulp_href": "/pulp/api/v3/pulp2repositories/92c6d1c8-718b-4ea9-8a23-b2386849c2c5/"
            }
        ]
    }


Reset migrated Pulp 3 data
--------------------------

.. note::
    Nothing will be reset or modified in any way in Pulp 2.
    Everything is removed for the specified plugins in Pulp 3, all data, migrated or not.

.. note::
    Migrated artifacts are untouched. If you are sure you want to remove them, please run the
    orphan cleanup task in Pulp 3.

There are cases, when one needs to run a migration from scratch (by default, it's always
incremental). E.g. some issue happened during the pulp2to3 migration which you are not able to
recover from.

All the commands should be run on Pulp 3 machine.


1. Create a :doc:`Migration Plan <../migration_plan>` for the set of plugins you would like to
reset.

.. code:: bash

    $ http POST :24817/pulp/api/v3/migration-plans/ plan='{"plugins": [{"type": "iso"}]}'

    HTTP/1.1 201 Created
    {
        "pulp_created": "2019-07-23T08:18:12.927007Z",
        "pulp_href": "/pulp/api/v3/migration-plans/59f8a786-c7d7-4e2b-ad07-701479d403c5/",
        "plan": "{ "plugins": [{"type": "iso"}]}"
    }

2. Use the ``pulp_href`` of the created Migration Plan and its ``reset/`` endpoint to reset Pulp 3
data.

.. code:: bash

    $ # reset Pulp 3 data to be able to migrate Pulp 2 ISO plugin from scratch
    $ http POST :24817/pulp/api/v3/migration-plans/59f8a786-c7d7-4e2b-ad07-701479d403c5/reset/

    HTTP/1.1 202 Accepted
    {
        "task": "/pulp/api/v3/tasks/55db2086-cf2e-438f-b5b7-cd0dbb7c8cf4/"
    }

.. note::
    Because this task removes data selectively, only for the plugins specified in the migration
    plan, it can take some time (~30 mins for a large system).

3. Now you can run your migration and it won't be an incremental run.

.. code:: bash

    $ http POST :24817/pulp/api/v3/migration-plans/59f8a786-c7d7-4e2b-ad07-701479d403c5/run/

    HTTP/1.1 202 Accepted
    {
        "task": "/pulp/api/v3/tasks/65db2086-cf2e-438f-b5b7-cd0dbb7c8cf5/"
    }

.. _level_of_deb_support:

The current level of Debian support
-----------------------------------

.. important::
   The migration plugins Debian support has not yet undergone large scale robustness testing, and should be considered to have "tech preview" status.

The migration plugin can be used to create a ``deb`` type migration plan to migrate any Pulp 2 APT repositories into a Pulp 3 instance.
Both simple and structured content can be migrated making the ``deb`` migration feature complete.

.. note::
   Since the Pulp 2 version of the ``pulp_deb`` plugin had nothing equivalent to verbatim publications, it is not possible to migrate content for Pulp 3 verbatim publications.
   Only the APT publisher (in both simple and structured mode) is supported for ``pulp_deb`` content that was migrated from Pulp 2.
