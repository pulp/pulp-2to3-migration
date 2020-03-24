Workflow
========

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


2. Use the ``pulp_href`` of the created Migration Plan to run the migration


.. code:: bash

    $ http POST :24817/pulp/api/v3/migration-plans/59f8a786-c7d7-4e2b-ad07-701479d403c5/run/

    HTTP/1.1 202 Accepted
    {
        "task": "/pulp/api/v3/tasks/55db2086-cf2e-438f-b5b7-cd0dbb7c8cf4/"
    }


3. For listing the mapping for Pulp 2 to Pulp 3

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
