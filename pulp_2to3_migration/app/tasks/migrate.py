import asyncio
import logging

from pulp_2to3_migration.app.pre_migration import (
    mark_removed_resources,
    pre_migrate_all_content,
    pre_migrate_all_without_content,
)

from pulp_2to3_migration.app.migration import (
    create_repo_versions,
    migrate_content,
    migrate_importers,
    migrate_repositories,
    migrate_distributors,
)
from pulp_2to3_migration.app.models import MigrationPlan
from pulp_2to3_migration.exceptions import PlanValidationError
from pulp_2to3_migration.pulp2 import connection


_logger = logging.getLogger(__name__)


def migrate_from_pulp2(migration_plan_pk, validate=False, dry_run=False):
    """
    Main task to migrate from Pulp 2 to Pulp 3.

    Schedule other tasks based on the specified Migration Plan.

    Args:
        migration_plan_pk (str): The migration plan PK.
        validate (bool): If True, don't migrate unless validation is successful.
        dry_run (bool): If True, nothing is migrated, only validation happens.
    """
    # MongoDB connection initialization
    connection.initialize()

    plan = MigrationPlan.objects.get(pk=migration_plan_pk)
    missing_resources = plan.get_missing_resources()

    if (validate or dry_run) and missing_resources:
        raise PlanValidationError(
            "Validation failed: resources missing {}".format(missing_resources)
        )

    if dry_run:
        return

    # TODO: if plan is empty for a plugin, only migrate downloaded content

    loop = asyncio.get_event_loop()
    loop.run_until_complete(pre_migrate_all_without_content(plan))
    loop.run_until_complete(mark_removed_resources(plan))
    loop.run_until_complete(migrate_repositories(plan))
    loop.run_until_complete(migrate_importers(plan))
    loop.run_until_complete(pre_migrate_all_content(plan))
    loop.run_until_complete(migrate_content(plan))
    loop.run_until_complete(create_repo_versions(plan))
    loop.run_until_complete(migrate_distributors(plan))
    loop.close()
