import logging

from collections import defaultdict

from pulpcore.plugin.models import CreatedResource, Task, TaskGroup

from pulp_2to3_migration.app.pre_migration import (
    delete_old_resources,
    mark_removed_resources,
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
from pulp_2to3_migration.pulp2.base import RepositoryContentUnit


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

    def get_repo_types(plan):
        """
        Create mappings for pulp 2 repository types.

        Identify type by inspecting content of a repo.
        One mapping is repo_id -> repo_type, the other is repo_type -> list of repo_ids.

        It's used later during pre-migration and identification of removed repos from pulp 2

        Args:
            plan(MigrationPlan): A Migration Plan

        Returns:
            repo_id_to_type(dict): mapping from a pulp 2 repo_id to a plugin/repo type
            type_to_repo_ids(dict): mapping from a plugin/repo type to the list of repo_ids

        """
        repo_id_to_type = {}
        type_to_repo_ids = defaultdict(set)

        # mapping content type -> plugin/repo type, e.g. 'docker_blob' -> 'docker'
        content_type_to_plugin = {}

        for plugin in plan.get_plugin_plans():
            for content_type in plugin.migrator.pulp2_content_models:
                content_type_to_plugin[content_type] = plugin.migrator.pulp2_plugin

            repos = set(plugin.get_repositories())
            repos |= set(plugin.get_importers_repos())
            repos |= set(plugin.get_distributors_repos())

            for repo in repos:
                repo_id_to_type[repo] = plugin.type
            type_to_repo_ids[plugin.type].update(repos)

        # TODO: optimizations.
        # It looks at each content at the moment. Potential optimizations:
        #  - Filter by repos from the plan
        #  - Query any but one record for a repo

        for rec in RepositoryContentUnit.objects().only('repo_id', 'unit_type_id'):
            repo_id = rec['repo_id']
            unit_type_id = rec['unit_type_id']

            # a type for a repo is already known or this content/repo type is not supported
            if repo_id in repo_id_to_type or unit_type_id not in content_type_to_plugin:
                continue
            plugin_name = content_type_to_plugin[unit_type_id]
            repo_id_to_type[repo_id] = plugin_name
            type_to_repo_ids[plugin_name].add(repo_id)

        return repo_id_to_type, type_to_repo_ids

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
    current_task = Task.current()
    current_task.task_group = task_group
    current_task.save()
    resource = CreatedResource(content_object=task_group)
    resource.save()

    # call it here and not inside steps below to generate mapping only once
    repo_id_to_type, type_to_repo_ids = get_repo_types(plan)

    # TODO: if plan is empty for a plugin, only migrate downloaded content

    pre_migrate_all_without_content(plan, type_to_repo_ids, repo_id_to_type)
    pre_migrate_all_content(plan)
    mark_removed_resources(plan, type_to_repo_ids)
    delete_old_resources(plan)
    migrate_repositories(plan)
    migrate_importers(plan)
    migrate_content(plan)
    create_repoversions_publications_distributions(plan)

    task_group.finish()
