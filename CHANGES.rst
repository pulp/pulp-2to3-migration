=========
Changelog
=========

..
    You should *NOT* be adding new change log entries to this file, this
    file is managed by towncrier. You *may* edit previous change logs to
    fix problems like typo corrections or such.
    To add a new change log entry, please see
    https://docs.pulpproject.org/en/3.0/nightly/contributing/git.html#changelog-update

    WARNING: Don't drop the next directive!

.. towncrier release notes start

0.2.0b1 (2020-03-24)
====================

Features
--------

- Migrate RPM packages to Pulp 3.
  `#6177 <https://pulp.plan.io/issues/6177>`_
- Add custom repo metadata migration.
  `#6283 <https://pulp.plan.io/issues/6283>`_
- As a user I can migrate modules and modules-defaults
  `#6321 <https://pulp.plan.io/issues/6321>`_


Bugfixes
--------

- Add awaiting for docker DC resolution and do not use does_batch.
  `#6084 <https://pulp.plan.io/issues/6084>`_
- Do not pre-migrate schema1 docker tags when there are 2 tags with same name witin a repo.
  `#6234 <https://pulp.plan.io/issues/6234>`_


Misc
----

- `#6172 <https://pulp.plan.io/issues/6172>`_, `#6173 <https://pulp.plan.io/issues/6173>`_, `#6174 <https://pulp.plan.io/issues/6174>`_, `#6175 <https://pulp.plan.io/issues/6175>`_, `#6176 <https://pulp.plan.io/issues/6176>`_, `#6178 <https://pulp.plan.io/issues/6178>`_


----


0.1.0rc1 (2020-02-28)
=====================

Bugfixes
--------

- Migrating large repository leads to unmigrated units.
  `#6103 <https://pulp.plan.io/issues/6103>`_
- Migrate mutable content.
  `#6186 <https://pulp.plan.io/issues/6186>`_


----


0.0.1rc1 (2020-02-11)
=====================

Features
--------

- Add pulp3_repository_href to pulp2repositories api.
  `#6053 <https://pulp.plan.io/issues/6053>`_
- Make pulp2 importer optional.
  `#6056 <https://pulp.plan.io/issues/6056>`_
- Migrate empty repos if the migration plan specifies them.
  `#6070 <https://pulp.plan.io/issues/6070>`_

Bugfixes
--------

- Handling missing plugin modules
  `#5820 <https://pulp.plan.io/issues/5820>`_
- Fix migration of multiple plugins.
  `#5978 <https://pulp.plan.io/issues/5978>`_
- Add error message for the importers that cannot be migrated.
  `#5984 <https://pulp.plan.io/issues/5984>`_
- Fix the bindings for publication and distribution hrefs fields on pulp2repositories API.
  `#6049 <https://pulp.plan.io/issues/6049>`_
- Fix rendering of the pulp2repositories after a failed migration.
  `#6058 <https://pulp.plan.io/issues/6058>`_
- Handle case when repos are removed and re-created.
  `#6062 <https://pulp.plan.io/issues/6062>`_
- Fix docker repo migration with a custom distributor.
  `#6097 <https://pulp.plan.io/issues/6097>`_
- Fix blobs and manifests relations on migration re-run.
  `#6099 <https://pulp.plan.io/issues/6099>`_


Misc
----

- `#6131 <https://pulp.plan.io/issues/6131>`_


----


0.0.1b1 (2020-01-25)
====================

Features
--------

- As a user, I can provide a Migration Plan.
- Migrate iso content.
- Migration plan resources are validated against MongoDB (i.e. that they exist).
  `#5319 <https://pulp.plan.io/issues/5319>`_
- Migrate on_demand content.
  `#5337 <https://pulp.plan.io/issues/5337>`_
- Migrate Pulp 2 repositories into Pulp 3 repo versions.
  `#5342 <https://pulp.plan.io/issues/5342>`_
- As a user, I can migrate Pulp 2 distributor into publication/distribution in Pulp 3
  `#5343 <https://pulp.plan.io/issues/5343>`_
- Migrate docker content.
  `#5363 <https://pulp.plan.io/issues/5363>`_
- Migration plans are respected.
  `#5450 <https://pulp.plan.io/issues/5450>`_
- Mark and take into account changed or removed pulp2 resources.
  `#5632 <https://pulp.plan.io/issues/5632>`_
- Adding a new endpoint to query the Pulp2-Pulp3 mapping for resources.
  `#5634 <https://pulp.plan.io/issues/5634>`_
- Update get_pulp3_repository_setup so repos are grouped by plugin type.
  `#5845 <https://pulp.plan.io/issues/5845>`_


Bugfixes
--------

- Migrate only those repo types that belong to the plugin that is being migrated
  `#5485 <https://pulp.plan.io/issues/5485>`_
- Fix bug preventing the serializer from accepting non-JSON data
  `#5546 <https://pulp.plan.io/issues/5546>`_
- Prevent migration of importers/distributors with an empty config.
  `#5551 <https://pulp.plan.io/issues/5551>`_
- Specify pulp2_distributor_repository_ids instead of distributor_ids
  `#5837 <https://pulp.plan.io/issues/5837>`_
- Importer or distributor can be migrated even if their repository is not.
  `#5852 <https://pulp.plan.io/issues/5852>`_
- Fix "local variable 'pulp2repo' referenced before assignment".
  `#5899 <https://pulp.plan.io/issues/5899>`_
- Fix repository type identification.
  `#5957 <https://pulp.plan.io/issues/5957>`_
- All requested repositories are migrated regardless of the time of the last run or a migration plan change.
  `#5980 <https://pulp.plan.io/issues/5980>`_


Improved Documentation
----------------------

- Switch to using `towncrier <https://github.com/hawkowl/towncrier>`_ for better release notes.
  `#5501 <https://pulp.plan.io/issues/5501>`_
- Add examples of a Migraiton plan.
  `#5849 <https://pulp.plan.io/issues/5849>`_


Deprecations and Removals
-------------------------

- Change `_id`, `_created`, `_last_updated`, `_href` to `pulp_id`, `pulp_created`, `pulp_last_updated`, `pulp_href`
  `#5457 <https://pulp.plan.io/issues/5457>`_


Misc
----

- `#4592 <https://pulp.plan.io/issues/4592>`_, `#5491 <https://pulp.plan.io/issues/5491>`_, `#5492 <https://pulp.plan.io/issues/5492>`_, `#5580 <https://pulp.plan.io/issues/5580>`_, `#5633 <https://pulp.plan.io/issues/5633>`_, `#5693 <https://pulp.plan.io/issues/5693>`_, `#5867 <https://pulp.plan.io/issues/5867>`_, `#6035 <https://pulp.plan.io/issues/6035>`_

