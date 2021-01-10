import logging

from pulpcore.plugin.models import (
    CreatedResource,
    GroupProgressReport,
    Task,
    TaskGroup,
)

from pulp_2to3_migration.app.pre_migration import (
    handle_outdated_resources,
    pre_migrate_all_content,
    pre_migrate_all_without_content,
)

from pulp_2to3_migration.app.migration import (
    create_repoversions_publications_distributions,
    migrate_content,
    migrate_importers,
    migrate_repositories,
)
from pulp_2to3_migration.app.models import MigrationPlan
from pulp_2to3_migration.exceptions import PlanValidationError
from pulp_2to3_migration.pulp2 import connection


_logger = logging.getLogger(__name__)


def migrate_from_pulp2(migration_plan_pk, validate=False, dry_run=False, skip_corrupted=False):
    """
    Main task to migrate from Pulp 2 to Pulp 3.

    Schedule other tasks based on the specified Migration Plan.

    Args:
        migration_plan_pk (str): The migration plan PK.
        validate (bool): If True, don't migrate unless validation is successful.
        dry_run (bool): If True, nothing is migrated, only validation happens.
        skip_corrupted (bool): If True, corrupted content is skipped during migration,
                               no task failure.
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

    task_group = TaskGroup(description="Migration Sub-tasks")
    task_group.save()
    GroupProgressReport(
        message="Repo version creation",
        code="create.repo_version",
        task_group=task_group).save()
    GroupProgressReport(
        message="Distribution creation",
        code="create.distribution",
        task_group=task_group).save()
    current_task = Task.current()
    current_task.task_group = task_group
    current_task.save()
    resource = CreatedResource(content_object=task_group)
    resource.save()

    # TODO: if plan is empty for a plugin, only migrate downloaded content

    pre_migrate_all_without_content(plan)
    pre_migrate_all_content(plan)
    handle_outdated_resources(plan)
    migrate_repositories(plan)
    migrate_importers(plan)
    migrate_content(plan, skip_corrupted=skip_corrupted)
    create_repoversions_publications_distributions(plan)

    task_group.finish()
