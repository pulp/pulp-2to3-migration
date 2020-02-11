# pulp-2to3-migration

A [Pulp 3](https://pulpproject.org/) plugin to migrate from Pulp 2 to Pulp 3.
Supported plugins:
 - Pulp 2 ISO can be migrated into Pulp 3 File.
 - Pulp 2 Docker can be migrated into Pulp 3 Container.
 - RPM plugin migration is planned and currently in development. 

### Requirements

* /var/lib/pulp is shared from Pulp 2 machine
* access to Pulp 2 database

### Configuration
On Pulp 2 machine:

1. Make sure MongoDB listens on the IP address accesible outside, it should be configured as
one of the `bindIP`s in /etc/mongod.conf.

2. Make sure /var/lib/pulp is on a shared filesystem.


On Pulp 3 machine:
1. Mount /var/lib/pulp to your Pulp 3 storage location. By default, it's /var/lib/pulp.

2. Configure your connection to MongoDB in /etc/pulp/settings.py. You can use the same configuration
 as you have in Pulp 2 (only seeds might need to be different, it depends on your setup).

E.g.
```python
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
```

### Installation

Clone the repository and install it.
```
$ git clone https://github.com/pulp/pulp-2to3-migration.git
$ pip install -e pulp-2to3-migration
```

Or add it to [the ansible installer](https://github.com/pulp/ansible-pulp) configuration like any
 other pulp plugin.


### User Guide

#### Migration Plan

To configure what to migrate to Pulp 3, one needs to define a Migration Plan (MP).
A MP defines which plugins to migrate and how.
Migration plugin is declarative, fully migrated content and repositories in Pulp 3 will
 correspond to the most recent MP which has been run.
 
 Type of a plugin specified in a MP is a Pulp 2 plugin. E.g. one needs to specify `iso` to
  migrate content and repositories into Pulp 3 File plugin.
 
 Examples of the migration plan:
 
  - Migrate all for a specific plugin

```json
{
  "plugins": [
    {
      "type": "iso"
    }
  ]
}
```

  - Migrate a pulp 2 repository `file` (into a Pulp 3 repository with one repository version
  ), using an importer from a pulp 2
   repository `file2`, and
   distributors from a repository `file` and `file2`
   
```json
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

```

#### Workflow

All the commands should be run on Pulp 3 machine.

1. Create a Migration Plan
```
$ # migrate content for Pulp 2 ISO plugin
$ http POST :24817/pulp/api/v3/migration-plans/ plan='{"plugins": [{"type": "iso"}]}'

HTTP/1.1 201 Created
{
    "pulp_created": "2019-07-23T08:18:12.927007Z",
    "pulp_href": "/pulp/api/v3/migration-plans/59f8a786-c7d7-4e2b-ad07-701479d403c5/",
    "plan": "{ \"plugins\": [{\"type\": \"iso\"}]}"
}

```

2. Use the ``pulp_href`` of the created Migration Plan to run the migration
```
$ http POST :24817/pulp/api/v3/migration-plans/59f8a786-c7d7-4e2b-ad07-701479d403c5/run/

HTTP/1.1 202 Accepted
{
    "task": "/pulp/api/v3/tasks/55db2086-cf2e-438f-b5b7-cd0dbb7c8cf4/"
}

```

3. For listing the mapping for Pulp 2 to Pulp 3
```
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

```

### Plugin Writer's Guide

If you are extending this migration tool to be able to migrate the plugin of your interest
from Pulp 2 to Pulp 3, here are some guidelines.


1. Create a migrator class (subclass the provided `Pulp2to3PluginMigrator` class). There should be
 one migrator class per plugin. Define all the necessary attributes and methods for it (see
  `Pulp2to3PluginMigrator` for more details)

2. Discovery of the plugins is done via entry_points. Add your migrator class defined in step 1
 to the list of the "migrators" entry_points in setup.py.

3. Add a Content model to communicate with Pulp 2.
 - It has to have a field `pulp2_type` which will correspond to the `_content_type_id` of your Content
 in Pulp 2. Don't forget to add it to `content_models` in step 1.

4. Add a Content model to pre-migrate Pulp 2 content to (subclass the provided `Pulp2to3Content`
class). It has to have:
 - a field `type` which will correspond to the `_content_type_id` of your Content in Pulp 2.
 - on a Meta class a `default_related_name` set to `<your pulp 2 content type>_detail_model`
 - a classmethod `pre_migrate_content_detail` (see `Pulp2to3Content` for more details)
 - a method `create_pulp3_content` (see `Pulp2to3Content` for more details)

 If your content has one artifact and if you are willing to use the default implementation of the
 first stage of DeclarativeContentMigration, on your Content model you also need:
 - an `expected_digests` property to provide expected digests for artifact creation/validation
 - an `expected_size` property to provide the expected size for artifact creation/validation
 - a `relative_path_for_content_artifact` property to provide the relative path for content
 artifact creation.

5. Subclass the provided `Pulp2to3Importer` class and define `migrate_to_pulp3` method which
creates a plugin Remote instance based on the provided pre-migrated `Pulp2Importer`.

6. Subclass the provided `Pulp2to3Distributor` class and define `migrate_to_pulp3` method which
creates a plugin Publication and/or Distribution instance (depends on the plugin) based on the
provided pre-migrated `Pulp2Distributor`.
