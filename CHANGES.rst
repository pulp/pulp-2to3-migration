=========
Changelog
=========

..
    You should *NOT* be adding new change log entries to this file, this
    file is managed by towncrier. You *may* edit previous change logs to
    fix problems like typo corrections or such.
    To add a new change log entry, please see
    https://docs.pulpproject.org/contributing/git.html#changelog-update

    WARNING: Don't drop the next directive!

.. towncrier release notes start

0.17.0 (2022-09-20)
===================

Bugfixes
--------

- Fixed issue where migration.py passes a Content object to remove_content(),
  which ends up breaking pulpcore's remove_content() further down the line with
  a traceback stating, 'Content' object has no attribute 'count'.

  Pulpcore's remove_content() will not face this issue anymore as it will now
  always receive a QuerySet object from migration.py.
  `#550 <https://github.com/pulp/pulp-2to3-migration/issues/550>`__
- Migration may stuck for many days when migrating an environment with massive number of rpms. This commit fixed the issue.
  `#568 <https://github.com/pulp/pulp-2to3-migration/issues/568>`__
- When pre-migrating errata, make query in batch to prevent the BSON too large error.
  `#572 <https://github.com/pulp/pulp-2to3-migration/issues/572>`__
- Fix invalid BSON size error when migrating docker contents

  The size limit for a single document in Mongodb is 16MB so
  migrating many docker tags could exceed this limit. This commit
  fixes this issue by fetching the docker tags in a specified
  batch size instead of fetching all and returning a large
  results into a single document.
  `#578 <https://github.com/pulp/pulp-2to3-migration/issues/578>`__


Improved Documentation
----------------------

- Added steps to remove the plugin and announced its EOL.
  Pulp-2to3-migration plugin reaches its EOL on December 31, 2022. The last supported pulpcore version is 3.19.
  `#534 <https://github.com/pulp/pulp-2to3-migration/issues/534>`__


----


0.16.0 (2022-03-15)
===================

Features
--------

- Added the `DEB_COMPONENT_BATCH_SIZE` setting, so users can individually control the batch size for this one to many type.
  `#9564 <https://github.com/pulp/pulp-2to3-migration/issues/9564>`__


Bugfixes
--------

- Try parsing advisory dates as unix timestamps before giving up.
  `#483 <https://github.com/pulp/pulp-2to3-migration/issues/483>`__
- Fixed a bug in the deb migration that caused migrated repos to lack content needed for structured publications in some circumstances.
  `#484 <https://github.com/pulp/pulp-2to3-migration/issues/484>`__
- Fixed DistributionTree (kickstart tree) migration for pulp_rpm 3.17+.

  Alma Linux 8 or CentOS 8 repos migration will no longer fail with:
  No declared artifact with relative path "images/boot.iso" (or ".treeinfo").
  `#491 <https://github.com/pulp/pulp-2to3-migration/issues/491>`__
- Escape django template syntax in xml when rendering filelist
  `#496 <https://github.com/pulp/pulp-2to3-migration/issues/496>`__
- Fixed local variable 'item' referenced before assignment
  `#497 <https://github.com/pulp/pulp-2to3-migration/issues/497>`__
- Taught mongo-connection how to deal with Really Big Queries. This addresses the cause of
  exceptions like `pymongo.errors.OperationFailure: Sort exceeded memory limit of 104857600 bytes`
  when migrating large collections.
  `#511 <https://github.com/pulp/pulp-2to3-migration/issues/511>`__
- Fixed ``'NoneType' object has no attribute 'delete'`` error during migration re-runs.
  `#8968 <https://github.com/pulp/pulp-2to3-migration/issues/8968>`__
- deb_components now use a default batch size of 50 to avoid CursorNotFound errors during pre_migration for this one to many type.
  `#9564 <https://github.com/pulp/pulp-2to3-migration/issues/9564>`__


----


0.15.0 (2021-11-11)
===================

Features
--------

- Added ``signing_service`` for (apt-)repository in Complex-MigrationPlan. This allows for a signing-service created before the migration to automatically be attached to the migrated repositories.
  `#9517 <https://pulp.plan.io/issues/9517>`__


Bugfixes
--------

- Fixed distibution tree migration issue "‘NoneType’ object has no attribute ‘url’".
  `#8862 <https://pulp.plan.io/issues/8862>`__
- Add batch_size to a pulp 2 query for content pre-migration of errata.
  `#9451 <https://pulp.plan.io/issues/9451>`__


Improved Documentation
----------------------

- Added a note about migration when Pulp 3 runs on a FIPS-enabled machine.
  `#7992 <https://pulp.plan.io/issues/7992>`__


Misc
----

- `#9209 <https://pulp.plan.io/issues/9209>`__, `#9458 <https://pulp.plan.io/issues/9458>`__


----


0.14.0 (2021-08-31)
===================

Bugfixes
--------

- Filtered out incomplete publications for the pulp2repositories/ endpoint.
  `#9242 <https://pulp.plan.io/issues/9242>`__
- Fixed migration of sles_auth_token
  `#9254 <https://pulp.plan.io/issues/9254>`__
- Fixed bug where sync tasks would open a lot of DB connections
  `#9283 <https://pulp.plan.io/issues/9283>`__
- Fixed remigration of publications after an unsuccessful or interrupted run.
  `#9295 <https://pulp.plan.io/issues/9295>`__


Misc
----

- `#8895 <https://pulp.plan.io/issues/8895>`__


----


0.13.0 (2021-08-06)
===================

Bugfixes
--------

- Fixed modular errata migration.
  `#8874 <https://pulp.plan.io/issues/8874>`__
- Add migration of gpgkeys-field for verification of debian-repos.
  `#8970 <https://pulp.plan.io/issues/8970>`__
- Fix migration for any clients that have applied the fix for #8893.
  `#8982 <https://pulp.plan.io/issues/8982>`__
- Strip leading slashes from Relative URL for deb-migrations.
  `#9184 <https://pulp.plan.io/issues/9184>`__


Deprecations and Removals
-------------------------

- Dropped support for Python 3.6 and 3.7.
  `#9038 <https://pulp.plan.io/issues/9038>`__


Misc
----

- `#9185 <https://pulp.plan.io/issues/9185>`__

----


0.12.1 (2021-07-02)
===================

Bugfixes
--------

- Fixed a bug causing deb migrations to fail if there are Pulp 2 importers without a releases field.
  `#8928 <https://pulp.plan.io/issues/8928>`__

----


0.12.0 (2021-06-17)
===================

Features
--------

- Started migrating relationship between repo and importer to Pulp 3.
  `#8626 <https://pulp.plan.io/issues/8626>`__


Improved Documentation
----------------------

- Taught 2to3 migration about changes in task-dispatching and Distributions.

  **NOTE**: To minimize any potential impact from this change, please make sure
  you've done a 2to3 migration after any Pulp2 changes to distributors **before**
  upgrading to this release.
  `#8522 <https://pulp.plan.io/issues/8522>`__

----


0.11.11 (2022-06-06)
====================

Bugfixes
--------

- Fixed issue where migration.py passes a Content object to remove_content(),
  which ends up breaking pulpcore's remove_content() further down the line with
  a traceback stating, 'Content' object has no attribute 'count'.

  Pulpcore's remove_content() will not face this issue anymore as it will now
  always receive a QuerySet object from migration.py.
  `#550 <https://pulp.plan.io/issues/550>`_


----


0.11.10 (2022-03-18)
====================

Bugfixes
--------

- Taught mongo-connection how to deal with Really Big Queries. This addresses the cause of
  exceptions like `pymongo.errors.OperationFailure: Sort exceeded memory limit of 104857600 bytes`
  when migrating large collections.
  `#511 <https://pulp.plan.io/issues/511>`_


----


0.11.9 (2022-01-14)
===================

Bugfixes
--------

- Escape django template syntax in xml when rendering filelist
  `#496 <https://pulp.plan.io/issues/496>`__
- Fixed local variable 'item' referenced before assignment
  `#497 <https://pulp.plan.io/issues/497>`__


----


0.11.8 (2022-01-07)
===================

Bugfixes
--------

- Fixed distribution tree migration for repositories with partial .treeinfo (e.g. most of CentOS 8 repositories).
  `#489 <https://github.com/pulp/pulp-2to3-migration/issues/489>`__

----


0.11.7 (2021-12-07)
===================

Bugfixes
--------

- Fixed ``'NoneType' object has no attribute 'delete'`` error during migration re-runs.
  (backported from #8968)
  `#9612 <https://pulp.plan.io/issues/9612>`__

----


0.11.6 (2021-11-17)
===================

Bugfixes
--------

- Fixed migration of sles_auth_token (backported from #9254)
  `#9456 <https://pulp.plan.io/issues/9456>`__
- Add batch_size to a pulp 2 query for content pre-migration of errata.
  (backported from #9451)
  `#9482 <https://pulp.plan.io/issues/9482>`__

----


0.11.5 (2021-09-10)
===================

Bugfixes
--------

- Fixed distibution tree migration issue "‘NoneType’ object has no attribute ‘url’".
  (backported from #8862)
  `#9372 <https://pulp.plan.io/issues/9372>`__

----


0.11.4 (2021-08-26)
===================

Bugfixes
--------

- Fixed remigration of publications after an unsuccessful or interrupted run.
  (backported from #9295)
  `#9296 <https://pulp.plan.io/issues/9296>`__
- Filtered out incomplete publications for the pulp2repositories/ endpoint.
  (backported from #9242)
  `#9297 <https://pulp.plan.io/issues/9297>`__

Misc
----

- `#9194 <https://pulp.plan.io/issues/9194>`__

----


0.11.3 (2021-08-02)
===================

Bugfixes
--------

- Fixed a bug causing deb migrations to fail if there are Pulp 2 importers without a releases field.
  (backported from #8928)
  `#8945 <https://pulp.plan.io/issues/8945>`__
- Added migration of gpgkeys-field for verification of debian-repos.
  (backported from #8970)
  `#9017 <https://pulp.plan.io/issues/9017>`__
- Fixed migration for any clients that have applied the fix for #8893.
  (backported from #8982)
  `#9109 <https://pulp.plan.io/issues/9109>`__
- Fixed modular errata migration.
  (backported from #8874)
  `#9173 <https://pulp.plan.io/issues/9173>`__
- Strip leading slashes from Relative URL for deb-migrations.
  (backported from #9184)
  `#9188 <https://pulp.plan.io/issues/9188>`__

----


0.11.2 (2021-06-14)
===================

Bugfixes
--------

- Fixed migration of CentOS8 distribution trees.
  `#8566 <https://pulp.plan.io/issues/8566>`__
- Fixed a problem when migrating one plugin after another will remove publications/distributions of the first one.
  `#8686 <https://pulp.plan.io/issues/8686>`__
- Ensure a checksum type of a package is used for publications when a checksum type was not explicitly configured in Pulp 2.

  If you plan to perform sync from the migrated Pulp 3 to a Pulp 2 instance, this fix is important, otherwise you can ignore it.
  If you've already started migration of the RPM plugin to Pulp 3, reset the migration for it and start again.
  `#8725 <https://pulp.plan.io/issues/8725>`__
- Fix migration of on_demand distribution (kickstart) trees when they do no have any images, e.g. CentOS 8 High Availability repo.
  `#8817 <https://pulp.plan.io/issues/8817>`__
- Pulp2 Content that does not have downloaded flag is marked as downloaded.
  `#8863 <https://pulp.plan.io/issues/8863>`__


----


0.11.1 (2021-05-04)
===================

Bugfixes
--------

- Stopped migrating unsupported metadata, like .zck, which could have been imported into some old Pulp 2 version.
  `#8400 <https://pulp.plan.io/issues/8400>`__
- Handled overlapping paths which might come from old pulp2 repositories.
  `#8582 <https://pulp.plan.io/issues/8582>`__
- Handled properly skipping of corrupted or missing docker content.
  `#8594 <https://pulp.plan.io/issues/8594>`__
- Fixed a bug in the deb pipeline that was preventing successfull skipping of corrupted content for migrations with ``skip_corrupted=True``.
  `#8612 <https://pulp.plan.io/issues/8612>`__
- Fixed migration of Pulp 2 deb importers without configured components or architectures
  `#8613 <https://pulp.plan.io/issues/8613>`__
- Fixed `total` counters for content migration.
  `#8621 <https://pulp.plan.io/issues/8621>`__
- Fixed Debian importer migration on a re-run.
  `#8653 <https://pulp.plan.io/issues/8653>`__


----


0.11.0 (2021-04-12)
===================

Features
--------

- Added a new configuration option `CONTENT_PREMIGRATION_BATCH_SIZE` to be able to adjust the content batch size if the system is slow.
  `#8470 <https://pulp.plan.io/issues/8470>`__


Misc
----

- `#6742 <https://pulp.plan.io/issues/6742>`__


----


0.10.0 (2021-03-23)
===================

Bugfixes
--------

- Fixed the case when some Pulp 2 content was removed and cleaned up between migration re-runs.
  `#7887 <https://pulp.plan.io/issues/7887>`__
- Fixed a migraiton failure when no importer was specified in the migration plan.
  `#8382 <https://pulp.plan.io/issues/8382>`__
- Fixed errata re-migration when it's been copied to a new repo in Pulp2 between migration re-runs.
  `#8417 <https://pulp.plan.io/issues/8417>`__
- Fixed the case when listing pulp2content/ endpoint using bindings would fail if content didn't have a storage path in Pulp 2.
  `#8436 <https://pulp.plan.io/issues/8436>`__


----


0.9.1 (2021-03-11)
==================

Bugfixes
--------

- Fixed a migration failure when no importer was specified in the migration plan.
  `#8389 <https://pulp.plan.io/issues/8389>`__


----


0.9.0 (2021-03-09)
==================

Bugfixes
--------

- Fixed re-migration cases when a distributor on an importer changed in the migration plan between re-runs.
  `#7889 <https://pulp.plan.io/issues/7889>`__
- Ensure trailing slash is present when assembling the url.
  `#8321 <https://pulp.plan.io/issues/8321>`__
- Fixed pulp2content unique-constraint to correctly handle a null repo-id field.
  `#8329 <https://pulp.plan.io/issues/8329>`__


Improved Documentation
----------------------

- Added docs on the value of fast storage volumes and adjusting the worker timeout values for both
  Pulp 2 and Pulp 3.
  `#7847 <https://pulp.plan.io/issues/7847>`__
- Updated docs to pulp-cli.
  `#8254 <https://pulp.plan.io/issues/8254>`__


Misc
----

- `#7009 <https://pulp.plan.io/issues/7009>`__, `#8288 <https://pulp.plan.io/issues/8288>`__, `#8314 <https://pulp.plan.io/issues/8314>`__


----


0.8.0 (2021-02-18)
==================

Features
--------

- Added the ability to migrate additional Debian content types needed for structured publishing.
  `#7865 <https://pulp.plan.io/issues/7865>`__
- The default configuration now contains the ALLOWED_CONTENT_CHECKSUMS setting with all checksum types supported in Pulp 2.
  `#8266 <https://pulp.plan.io/issues/8266>`__


Bugfixes
--------

- Fixed the re-run times when repositories/importers/distributors haven't changed much since the last run.
  `#7779 <https://pulp.plan.io/issues/7779>`__
- Fixed an edge-case failure in erratum-migration when doing repeated migrations.
  `#8166 <https://pulp.plan.io/issues/8166>`__
- Fixed distributor re-migration case when it was changed in Pulp 2 between migration plan runs.
  `#8195 <https://pulp.plan.io/issues/8195>`__
- Fixed openapi schema for reset/ endpoint. Bindings no longer require `plan` parameter.
  `#8211 <https://pulp.plan.io/issues/8211>`__


Improved Documentation
----------------------

- Added a note that ALLOWED_CONTENT_CHECKSUMS is strongly recommended to allow all supported checksum types, and can be adjusted after the migration.
  `#8266 <https://pulp.plan.io/issues/8266>`__


Misc
----

- `#8137 <https://pulp.plan.io/issues/8137>`__


----


0.7.0 (2021-02-04)
==================

Bugfixes
--------

- Multi-artifact content aren't (not) skipped properly when some artifacts are unavailable.
  `#7681 <https://pulp.plan.io/issues/7681>`__
- Taught pre-migration to order content by last-updated.

  This lets a migration recover reliably from fatal errors during migration attempts.
  NOTE: this fix assumes the Pulp2 instance is at least at 2.21.5. Earlier versions are
  missing an index in the Mongo database that makes the ordering possible.
  `#7781 <https://pulp.plan.io/issues/7781>`__
- Fix an error migrating module content with no "stream" or "profile" information specified, as is allowed by the spec.
  `#7846 <https://pulp.plan.io/issues/7846>`__
- No longer generate sqlite metadata when publishing unless the Pulp 2 configuration specified to do so.
  `#7851 <https://pulp.plan.io/issues/7851>`__
- Fixed Pulp2Content serialization when filters are applied.
  `#7994 <https://pulp.plan.io/issues/7994>`__
- Taught rpm to warn and continue if a Distribution is missing a treeinfo file.
  `#8084 <https://pulp.plan.io/issues/8084>`__


Misc
----

- `#6516 <https://pulp.plan.io/issues/6516>`__, `#7903 <https://pulp.plan.io/issues/7903>`__, `#7934 <https://pulp.plan.io/issues/7934>`__, `#7966 <https://pulp.plan.io/issues/7966>`__, `#7998 <https://pulp.plan.io/issues/7998>`__, `#7999 <https://pulp.plan.io/issues/7999>`__, `#8040 <https://pulp.plan.io/issues/8040>`__, `#8041 <https://pulp.plan.io/issues/8041>`__


----


0.6.0 (2020-12-04)
==================

Features
--------

- Added an option to skip corrupted or missing Pulp 2 content.
  `#7538 <https://pulp.plan.io/issues/7538>`__
- Added a reset/ endpoint to be able to run migration from scratch.
  `#7714 <https://pulp.plan.io/issues/7714>`__
- Added support to migrate Debian packages (tech preview).
  `#7863 <https://pulp.plan.io/issues/7863>`__


Bugfixes
--------

- Fixed distribution serialization.
  `#7809 <https://pulp.plan.io/issues/7809>`__


Misc
----

- `#7823 <https://pulp.plan.io/issues/7823>`__


----


0.5.1 (2020-10-27)
==================

Bugfixes
--------

- Fixed a bug where RPM content metadata is not properly migrated to Pulp 3.
  `#7625 <https://pulp.plan.io/issues/7625>`__


----


0.5.0 (2020-10-13)
==================

Bugfixes
--------

- Publications and Distributions are re-created on migration re-run for repos that contain mutable content,
  and pre-migrated mutable content is no longer deleted and recreated every time.
  `#7280 <https://pulp.plan.io/issues/7280>`__
- Fixed a bug where PULP_MANIFEST was being created outside of the worker's working directory.
  `#7693 <https://pulp.plan.io/issues/7693>`__
- Sped up repository pre-migration by skipping the repository content relations pre-migration when nothing changed in a repository.
  `#7694 <https://pulp.plan.io/issues/7694>`__
- Made content migration significantly faster on low-spec machines w/ HDD backed database storage.
  `#7699 <https://pulp.plan.io/issues/7699>`__


----


0.4.1 (2020-10-09)
==================

Bugfixes
--------

- Fix the bindings for publication and distribution hrefs fields on pulp2repositories API.
  `#7679 <https://pulp.plan.io/issues/7679>`__


----


0.4.0 (2020-10-07)
==================

Bugfixes
--------

- Fixed a distribution migration case when a repository in Pulp 2 has been recreated.
  `#7080 <https://pulp.plan.io/issues/7080>`__
- Stopped logging warnings if at least one LCE per content migrated.
  `#7193 <https://pulp.plan.io/issues/7193>`__
- Fixed metadata checksum type configuration re-migration.
  `#7417 <https://pulp.plan.io/issues/7417>`__
- Fixed re-migration issue when pulp 2 importer changed a feed.
  `#7418 <https://pulp.plan.io/issues/7418>`__
- Fixed validation of the distributor missing resources in the migration plan.
  `#7488 <https://pulp.plan.io/issues/7488>`__
- Fix custom metadata migration when the same metadata is present under different paths in different repositories.
  `#7489 <https://pulp.plan.io/issues/7489>`__
- Fixed high memory usage when migrating large amounts of content (300,000+).
  `#7490 <https://pulp.plan.io/issues/7490>`__
- Removed comps content types from future_types.
  `#7518 <https://pulp.plan.io/issues/7518>`__
- Fixed migration of lazy multi-artifact content not present in a repository in the plan.
  `#7562 <https://pulp.plan.io/issues/7562>`__


----


0.3.0 (2020-08-26)
==================

Features
--------

- Added GroupProgressReport tracking during the migration.
  `#6769 <https://pulp.plan.io/issues/6769>`__
- Make the migration plugin compatible with pulp_container 2.0
  `#7365 <https://pulp.plan.io/issues/7365>`__


Bugfixes
--------

- Significantly improved performance of partial migrations (when some content / repos has been migrated already).
  `#6111 <https://pulp.plan.io/issues/6111>`__
- Fixed migration of a distribution tree if it has a treeinfo and not .treeinfo
  `#6951 <https://pulp.plan.io/issues/6951>`__
- Fixed cause of view_name warnings during (re)start of Pulp services.
  `#7154 <https://pulp.plan.io/issues/7154>`__
- Marked all Pulp2LCEs as migrated for distribution tree migration.
  `#7260 <https://pulp.plan.io/issues/7260>`__


Misc
----

- `#6963 <https://pulp.plan.io/issues/6963>`__


----


0.2.1 (2020-08-26)
==================

Bugfixes
--------

- Updated migration of file remote url to point to the Manifest.
  `#7264 <https://pulp.plan.io/issues/7264>`__


----


0.2.0 (2020-08-20)
==================

Bugfixes
--------

- Fix exceptions thrown by content migration not being bubbled up through the task.
  `#6469 <https://pulp.plan.io/issues/6469>`__


----


0.2.0b6 (2020-07-24)
====================

Features
--------

- Add support for migrating SLES12+ repos which require auth token.
  `#6927 <https://pulp.plan.io/issues/6927>`__


Bugfixes
--------

- Fixed distribution tree migration when a distribution tree is present in multiple repositories.
  `#6950 <https://pulp.plan.io/issues/6950>`__
- Fix a bug where errata were not always migrated for new repositories.
  `#7092 <https://pulp.plan.io/issues/7092>`__
- Fix yum metadata files not being migrated.
  `#7093 <https://pulp.plan.io/issues/7093>`__
- Fix an issue causing extremely high memory usage as # of content scale up.
  `#7152 <https://pulp.plan.io/issues/7152>`__
- Fixed a bug where migrated repositories could have multiple different copies of an errata.
  `#7165 <https://pulp.plan.io/issues/7165>`__


Misc
----

- `#7206 <https://pulp.plan.io/issues/7206>`__


----


0.2.0b5 (2020-07-03)
====================

Bugfixes
--------

- Fixed distribution tree re-migration.
  `#6949 <https://pulp.plan.io/issues/6949>`__
- Fixed RPM migration when its remote is not migrated.
  `#7078 <https://pulp.plan.io/issues/7078>`__


Misc
----

- `#6939 <https://pulp.plan.io/issues/6939>`__, `#7020 <https://pulp.plan.io/issues/7020>`__


----


0.2.0b4 (2020-06-23)
====================

Features
--------

- Migrate checksum_type configuration for an RPM publication.
  `#6813 <https://pulp.plan.io/issues/6813>`__


Bugfixes
--------

- Fixed Ruby bindings generation.
  `#7016 <https://pulp.plan.io/issues/7016>`__


----


0.2.0b3 (2020-06-17)
====================

Features
--------

- Slightly improve performance by allowing repos to be migrated in parallel.
  `#6374 <https://pulp.plan.io/issues/6374>`__
- As a user, I can track Remotes and not remigrate them on every run.
  `#6375 <https://pulp.plan.io/issues/6375>`__
- Track Publications and Distributions, recreate if needed and not on every run.
  `#6376 <https://pulp.plan.io/issues/6376>`__


Bugfixes
--------

- Expose pulp3_repository_version on pulp2content if it is available.
  `#6580 <https://pulp.plan.io/issues/6580>`__
- Ensure that only one migration plan can be run at a time.
  `#6639 <https://pulp.plan.io/issues/6639>`__
- Fixed `UnboundLocalError` during migration of a repo with a custom name.
  `#6640 <https://pulp.plan.io/issues/6640>`__
- Fix an issue where a migration with many plugin types would crash on execution.
  `#6754 <https://pulp.plan.io/issues/6754>`__
- Fixed distribution creation when a distributor is from a repo which is not being migrated.
  `#6853 <https://pulp.plan.io/issues/6853>`__
- Fixed migration of a sub-set of previously migrated repos.
  `#6886 <https://pulp.plan.io/issues/6886>`__
- Handle already-migrated 're-created' pulp2 repos
  `#6887 <https://pulp.plan.io/issues/6887>`__
- Fixed marking of old distributors, when distributor only is migrated without the repo.
  `#6932 <https://pulp.plan.io/issues/6932>`__
- Fixed case when a publication is shared by multiple distributions.
  `#6947 <https://pulp.plan.io/issues/6947>`__
- Set pulp3_repo relation for all the cases, including remigration.
  `#6964 <https://pulp.plan.io/issues/6964>`__
- Fixed incorrect pulp3_repo_version href for advisories after remigration.
  `#6966 <https://pulp.plan.io/issues/6966>`__
- Fix comps migration when repo is recreated between the migration runs.
  `#6980 <https://pulp.plan.io/issues/6980>`__


----


0.2.0b2 (2020-04-22)
====================

Features
--------

- Migrate errata content.
  `#6178 <https://pulp.plan.io/issues/6178>`__
- As a user I can migrate comps content into pulp3.
  `#6358 <https://pulp.plan.io/issues/6358>`__
- As a user I can migrate SRPMS.
  `#6388 <https://pulp.plan.io/issues/6388>`__
- Improve performance by looking only at lazy content types and not through all the migrated content.
  `#6499 <https://pulp.plan.io/issues/6499>`__


Bugfixes
--------

- Set properly relative_path Pulp2YumRepoMetadataFile content_artifact.
  `#6400 <https://pulp.plan.io/issues/6400>`__


Misc
----

- `#6199 <https://pulp.plan.io/issues/6199>`__, `#6200 <https://pulp.plan.io/issues/6200>`__, `#6201 <https://pulp.plan.io/issues/6201>`__


----


0.2.0b1 (2020-03-24)
====================

Features
--------

- Migrate RPM packages to Pulp 3.
  `#6177 <https://pulp.plan.io/issues/6177>`__
- Add custom repo metadata migration.
  `#6283 <https://pulp.plan.io/issues/6283>`__
- As a user I can migrate modules and modules-defaults
  `#6321 <https://pulp.plan.io/issues/6321>`__


Bugfixes
--------

- Add awaiting for docker DC resolution and do not use does_batch.
  `#6084 <https://pulp.plan.io/issues/6084>`__


Misc
----

- `#6172 <https://pulp.plan.io/issues/6172>`__, `#6173 <https://pulp.plan.io/issues/6173>`__, `#6174 <https://pulp.plan.io/issues/6174>`__, `#6175 <https://pulp.plan.io/issues/6175>`__, `#6176 <https://pulp.plan.io/issues/6176>`__, `#6178 <https://pulp.plan.io/issues/6178>`__


0.1.0 (2020-03-24)
==================

Bugfixes
--------

- Do not pre-migrate schema1 docker tags when there are 2 tags with same name witin a repo.
  `#6234 <https://pulp.plan.io/issues/6234>`__


Improved Documentation
----------------------

- Moved README to readthedocs website.
  `#6145 <https://pulp.plan.io/issues/6145>`__


----


0.1.0rc1 (2020-02-28)
=====================

Bugfixes
--------

- Migrating large repository leads to unmigrated units.
  `#6103 <https://pulp.plan.io/issues/6103>`__
- Migrate mutable content.
  `#6186 <https://pulp.plan.io/issues/6186>`__


----


0.0.1rc1 (2020-02-11)
=====================

Features
--------

- Add pulp3_repository_href to pulp2repositories api.
  `#6053 <https://pulp.plan.io/issues/6053>`__
- Make pulp2 importer optional.
  `#6056 <https://pulp.plan.io/issues/6056>`__
- Migrate empty repos if the migration plan specifies them.
  `#6070 <https://pulp.plan.io/issues/6070>`__

Bugfixes
--------

- Handling missing plugin modules
  `#5820 <https://pulp.plan.io/issues/5820>`__
- Fix migration of multiple plugins.
  `#5978 <https://pulp.plan.io/issues/5978>`__
- Add error message for the importers that cannot be migrated.
  `#5984 <https://pulp.plan.io/issues/5984>`__
- Fix the bindings for publication and distribution hrefs fields on pulp2repositories API.
  `#6049 <https://pulp.plan.io/issues/6049>`__
- Fix rendering of the pulp2repositories after a failed migration.
  `#6058 <https://pulp.plan.io/issues/6058>`__
- Handle case when repos are removed and re-created.
  `#6062 <https://pulp.plan.io/issues/6062>`__
- Fix docker repo migration with a custom distributor.
  `#6097 <https://pulp.plan.io/issues/6097>`__
- Fix blobs and manifests relations on migration re-run.
  `#6099 <https://pulp.plan.io/issues/6099>`__


Misc
----

- `#6131 <https://pulp.plan.io/issues/6131>`__


----


0.0.1b1 (2020-01-25)
====================

Features
--------

- As a user, I can provide a Migration Plan.
- Migrate iso content.
- Migration plan resources are validated against MongoDB (i.e. that they exist).
  `#5319 <https://pulp.plan.io/issues/5319>`__
- Migrate on_demand content.
  `#5337 <https://pulp.plan.io/issues/5337>`__
- Migrate Pulp 2 repositories into Pulp 3 repo versions.
  `#5342 <https://pulp.plan.io/issues/5342>`__
- As a user, I can migrate Pulp 2 distributor into publication/distribution in Pulp 3
  `#5343 <https://pulp.plan.io/issues/5343>`__
- Migrate docker content.
  `#5363 <https://pulp.plan.io/issues/5363>`__
- Migration plans are respected.
  `#5450 <https://pulp.plan.io/issues/5450>`__
- Mark and take into account changed or removed pulp2 resources.
  `#5632 <https://pulp.plan.io/issues/5632>`__
- Adding a new endpoint to query the Pulp2-Pulp3 mapping for resources.
  `#5634 <https://pulp.plan.io/issues/5634>`__
- Update get_pulp3_repository_setup so repos are grouped by plugin type.
  `#5845 <https://pulp.plan.io/issues/5845>`__


Bugfixes
--------

- Migrate only those repo types that belong to the plugin that is being migrated
  `#5485 <https://pulp.plan.io/issues/5485>`__
- Fix bug preventing the serializer from accepting non-JSON data
  `#5546 <https://pulp.plan.io/issues/5546>`__
- Prevent migration of importers/distributors with an empty config.
  `#5551 <https://pulp.plan.io/issues/5551>`__
- Specify pulp2_distributor_repository_ids instead of distributor_ids
  `#5837 <https://pulp.plan.io/issues/5837>`__
- Importer or distributor can be migrated even if their repository is not.
  `#5852 <https://pulp.plan.io/issues/5852>`__
- Fix "local variable 'pulp2repo' referenced before assignment".
  `#5899 <https://pulp.plan.io/issues/5899>`__
- Fix repository type identification.
  `#5957 <https://pulp.plan.io/issues/5957>`__
- All requested repositories are migrated regardless of the time of the last run or a migration plan change.
  `#5980 <https://pulp.plan.io/issues/5980>`__


Improved Documentation
----------------------

- Switch to using `towncrier <https://github.com/hawkowl/towncrier>`__ for better release notes.
  `#5501 <https://pulp.plan.io/issues/5501>`__
- Add examples of a Migraiton plan.
  `#5849 <https://pulp.plan.io/issues/5849>`__


Deprecations and Removals
-------------------------

- Change `__id`, `__created`, `__last_updated`, `__href` to `pulp_id`, `pulp_created`, `pulp_last_updated`, `pulp_href`
  `#5457 <https://pulp.plan.io/issues/5457>`__


Misc
----

- `#4592 <https://pulp.plan.io/issues/4592>`__, `#5491 <https://pulp.plan.io/issues/5491>`__, `#5492 <https://pulp.plan.io/issues/5492>`__, `#5580 <https://pulp.plan.io/issues/5580>`__, `#5633 <https://pulp.plan.io/issues/5633>`__, `#5693 <https://pulp.plan.io/issues/5693>`__, `#5867 <https://pulp.plan.io/issues/5867>`__, `#6035 <https://pulp.plan.io/issues/6035>`__
