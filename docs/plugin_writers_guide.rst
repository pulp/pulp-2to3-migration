Plugin Writer's Guide
=====================

If you are extending this migration tool to be able to migrate the plugin of your interest
from Pulp 2 to Pulp 3, here are some guidelines.


1. Create a migrator class (subclass the provided ``Pulp2to3PluginMigrator`` class). There should be
one migrator class per plugin. Define all the necessary attributes and methods for it (see
``Pulp2to3PluginMigrator`` for more details)

2. Discovery of the plugins is done via entry_points. Add your migrator class defined in step 1
to the list of the ``migrators`` entry_points in ``setup.py``.

3. Add a Content model to communicate with Pulp 2.

* It has to have a field ``TYPE_ID`` which will correspond to the ``_content_type_id`` of your
  Content in Pulp 2. Don't forget to add it to ``pulp2_content_models`` in step 1.

4. Add a Content model to pre-migrate Pulp2 content to (subclass the provided ``Pulp2to3Content``
class). It has to have:

* a field ``pulp2_type`` which will correspond to the ``_content_type_id`` of your Content in Pulp 2.
* on a Meta class a ``default_related_name`` set to ``<your pulp 2 content type>_detail_model``
* a classmethod ``pre_migrate_content_detail`` (see ``Pulp2to3Content`` for more details)
* a coroutine ``create_pulp3_content`` (see ``Pulp2to3Content`` for more details)

Don't forget to add this Content model to your migrator class.

If your content has one artifact and if you are willing to use the default implementation of the
first stage of DeclarativeContentMigration, on your Content model you also need:

* an ``expected_digests`` property to provide expected digests for artifact creation/validation
* an ``expected_size`` property to provide the expected size for artifact creation/validation
* a ``relative_path_for_content_artifact`` property to provide the relative path for content
  artifact creation.

5. Subclass the provided ``Pulp2to3Importer`` class and define ``migrate_to_pulp3`` method which
creates a plugin Remote instance based on the provided pre-migrated ``Pulp2Importer``.

6. Subclass the provided ``Pulp2to3Distributor`` class and define ``migrate_to_pulp3`` method which
creates a plugin Publication and/or Distribution instance (depends on the plugin) based on the
provided pre-migrated ``Pulp2Distributor``.