import asyncio
import logging

from pulp_2to3_migration.app.pre_migration import (
    pre_migrate_all_content,
    pre_migrate_all_without_content,
)

from pulp_2to3_migration.app.migration import (
    migrate_content,
    migrate_importers,
    migrate_repositories,
)
from pulp_2to3_migration.app.models import MigrationPlan
from pulp_2to3_migration.pulp2 import connection


_logger = logging.getLogger(__name__)


def migrate_from_pulp2(migration_plan_pk, dry_run=False):
    """
    Main task to migrate from Pulp 2 to Pulp 3.

    Schedule other tasks based on the specified Migration Plan.

    Args:
        migration_plan_pk (str): The migration plan PK.
        dry_run (bool): If True, nothing is migrated, only validation happens.
    """
    plan = MigrationPlan.objects.get(pk=migration_plan_pk)
    if dry_run:
        _logger.debug('Running in a dry-run mode.')
        # TODO: Migration Plan validation
        return

    # MongoDB connection initialization
    connection.initialize()

    # TODO: Migration Plan parsing and validation
    # For now, the list of plugins to migrate is hard-coded.
    plugins_to_migrate = ['iso']


    loop = asyncio.get_event_loop()
    loop.run_until_complete(pre_migrate_all_without_content(plan))
    loop.run_until_complete(migrate_repositories())
    loop.run_until_complete(migrate_importers(plugins_to_migrate))
    loop.run_until_complete(pre_migrate_all_content(plugins_to_migrate))
    loop.run_until_complete(migrate_content(plugins_to_migrate))  # without RemoteArtifacts yet
#    loop.run_until_complete(create_repo_versions())
#    loop.run_until_complete(migrate_distributors(plugins_to_migrate))
    loop.close()
