Migration Plan
==============

To configure what to migrate to Pulp 3, one needs to define a Migration Plan (MP).
A MP defines which plugins to migrate and how.
Migration plugin is declarative, fully migrated content and repositories in Pulp 3 will
correspond to the most recent MP which has been run.

.. warning::
    It's expected that Pulp 3 hasn't been used for a specific plugin before the migration.
    The pulp-2to3-migration can remove some Pulp 3 data related to a plugin which is being migrated, or there can be a clash in naming or distribution paths.
    E.g. It is OK to migrate RPM plugin from Pulp 2 to Pulp 3, if you used (or maybe migrated earlier) pulp_file, and pulp_rpm 3.x hasn't been used.
    It is NOT OK, to migrate RPM plugin from Pulp 2 to Pulp 3, if you used  pulp_rpm 3.x before.

.. note::
    It is possible to have orphaned content in Pulp 3 after multiple migration re-runs. After the
    migration is fully complete, run orphan cleanup task in Pulp 3 to remove content which is not a
    part of any repository version.

The type of a plugin specified in a MP is a Pulp 2 plugin. E.g. one needs to specify ``iso`` to
migrate Pulp 2 ISO content and repositories into Pulp 3 File plugin.

Examples of the migration plan:

* Migrate all for a specific plugin

.. code:: json

    {
      "plugins": [
        {
          "type": "iso"
        }
      ]
    }


* Migrate a pulp 2 repository ``file`` (into a Pulp 3 repository with one repository version),
  using an importer from a pulp 2 repository ``file2``, and distributors from a repository ``file``
  and ``file2``

.. code:: json

    {
      "plugins": [
        {
          "type": "iso",
          "repositories": [
            {
              "name": "file",
              "repository_versions": [
                {
                  "pulp2_repository_id": "file",
                  "pulp2_distributor_repository_ids": [
                    "file", "file2"
                  ]
                }
              ],
              "pulp2_importer_repository_id": "file2"
            }
          ]
        }
      ]
    }
