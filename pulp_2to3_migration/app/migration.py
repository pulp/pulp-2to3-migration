import asyncio
import logging

from pulpcore.plugin.models import (
    Content,
    ProgressReport,
)

from pulp_2to3_migration.app.models import (
    Pulp2Content,
    Pulp2Importer,
    Pulp2RepoContent,
    Pulp2Repository,
)
from pulp_2to3_migration.app.plugin import PLUGIN_MIGRATORS

_logger = logging.getLogger(__name__)


async def migrate_content(plan):
    """
    A coroutine to initiate content migration for each plugin.

    Args:
         plan (MigrationPlan): Migration Plan to use
    """
    content_migration_coros = []
    plugins_to_migrate = plan.get_plugins()

    progress_data = dict(message='Migrating content to Pulp 3', code='migrating.content', total=0)
    with ProgressReport(**progress_data) as pb:
        # schedule content migration into Pulp 3 using pre-migrated Pulp 2 content
        for plugin in plugins_to_migrate:
            plugin_migrator = PLUGIN_MIGRATORS.get(plugin)
            content_migration_coros.append(plugin_migrator.migrate_content_to_pulp3())

            # only used for progress bar counters
            content_types = plugin_migrator.content_models.keys()
            pulp2content_qs = Pulp2Content.objects.filter(pulp2_content_type_id__in=content_types,
                                                          pulp3_content=None)
            pb.total += pulp2content_qs.count()
        pb.save()

        await asyncio.wait(content_migration_coros)

        pb.done = pb.total


async def migrate_repositories(plan):
    """
    A coroutine to migrate pre-migrated repositories.
    """

    repos_to_create = plan.get_pulp3_repository_setup().keys()
    progress_data = dict(
        message='Creating repositories in Pulp 3', code='creating.repositories', total=0
    )
    with ProgressReport(**progress_data) as pb:
        pulp2repos_qs = Pulp2Repository.objects.filter(pulp3_repository_version=None)

        # no specific migration plan for repositories
        if not repos_to_create:
            pb.total += pulp2repos_qs.count()
            pb.save()

            for pulp2repo in pulp2repos_qs:
                pulp3_repo_name = pulp2repo.pulp2_repo_id
                repository_class = PLUGIN_MIGRATORS.get(pulp2repo.type).pulp3_repository
                repo, created = repository_class.objects.get_or_create(
                    name=pulp3_repo_name,
                    description=pulp2repo.pulp2_description)
                if created:
                    pb.increment()
                else:
                    pb.total -= 1
                    pb.save()

        # specific migration plan for repositories
        else:
            pb.total += len(repos_to_create)
            pb.save()

            for pulp3_repo_name in repos_to_create:
                try:
                    pulp2repo = pulp2repos_qs.get(pulp2_repo_id=pulp3_repo_name)
                except Pulp2Repository.DoesNotExist:
                    description = pulp3_repo_name
                else:
                    description = pulp2repo.pulp2_description

                repository_class = PLUGIN_MIGRATORS.get(pulp2repo.type).pulp3_repository
                repo, created = repository_class.objects.get_or_create(
                    name=pulp3_repo_name,
                    description=description)
                if created:
                    pb.increment()
                else:
                    pb.total -= 1
                    pb.save()


async def migrate_importers(plan):
    """
    A coroutine to migrate pre-migrated importers.

    Args:
        plan (MigrationPlan): Migration Plan to use.
    """
    # gather all needed plugin importer migrators
    importer_migrators = {}
    plugins_to_migrate = plan.get_plugins()

    for plugin, plugin_migrator in PLUGIN_MIGRATORS.items():
        if plugin not in plugins_to_migrate:
            continue
        importer_migrators.update(**plugin_migrator.importer_migrators)

    progress_data = dict(
        message='Migrating importers to Pulp 3', code='migrating.importers', total=0
    )
    with ProgressReport(**progress_data) as pb:
        # Temp fix until https://pulp.plan.io/issues/5485 is done
        pulp2importers_qs = Pulp2Importer.objects.filter(
            pulp2_type_id__in=importer_migrators.keys(),
            pulp3_remote=None)
        pb.total += pulp2importers_qs.count()
        pb.save()

        for pulp2importer in pulp2importers_qs:
            importer_migrator = importer_migrators.get(pulp2importer.pulp2_type_id)
            remote, created = await importer_migrator.migrate_to_pulp3(pulp2importer)
            pulp2importer.pulp3_remote = remote
            pulp2importer.is_migrated = True
            pulp2importer.save()
            if created:
                pb.increment()
            else:
                pb.total -= 1
                pb.save()


async def create_repo_versions(plan):
    """
    A coroutine to create repository versions.

    Content to a repo version is added based on pre-migrated RepoContentUnit and info provided
    in the migration plan.

    Args:
        plan (MigrationPlan): Migration Plan to use.
    """
    def create_repo_version(pulp3_repo_name, pulp2_repo):
        """
        Create a repo version based on a pulp2 repository

        Args:
            pulp3_repo_name(str): repository name in Pulp 3
            pulp2_repo(Pulp2Repository): a pre-migrated repository to create a repo version for
        """

        repository_class = PLUGIN_MIGRATORS.get(pulp2_repo.type).pulp3_repository
        pulp3_repo = repository_class.objects.get(name=pulp3_repo_name)
        unit_ids = Pulp2RepoContent.objects.filter(pulp2_repository=pulp2_repo).values_list(
            'pulp2_unit_id', flat=True)
        incoming_content = set(Pulp2Content.objects.filter(pulp2_id__in=unit_ids).only(
            'pulp3_content').values_list('pulp3_content__pk', flat=True))

        with pulp3_repo.new_version() as new_version:
            repo_content = set(new_version.content.values_list('pk', flat=True))
            to_add = incoming_content - repo_content
            to_delete = repo_content - incoming_content
            new_version.add_content(Content.objects.filter(pk__in=to_add))
            new_version.remove_content(Content.objects.filter(pk__in=to_delete))
        return new_version

    pulp3_repo_setup = plan.get_pulp3_repository_setup()
    if not pulp3_repo_setup:
        # create one repo version for each pulp 2 repo
        # TODO: filter by plugin type (only migrate repos for plugins in the MP)
        repos_to_migrate = Pulp2Repository.objects.filter(is_migrated=False)
        for pulp2_repo in repos_to_migrate:
            repo_version = create_repo_version(pulp2_repo.pulp2_repo_id, pulp2_repo)
            pulp2_repo.pulp3_repository_version = repo_version
            pulp2_repo.is_migrated = True
            pulp2_repo.save()
    else:
        for repo_name in pulp3_repo_setup:
            repo_versions_setup = pulp3_repo_setup[repo_name]['versions']
            for pulp2_repo_id in repo_versions_setup:
                repo_to_migrate = Pulp2Repository.objects.get(pulp2_repo_id=pulp2_repo_id)
                if not repo_to_migrate.is_migrated:
                    # it's possible to have a random order of the repo versions (after migration
                    # re-run, a repo can be changed in pulp 2 and it might not be for the last
                    # repo version)
                    repo_version = create_repo_version(repo_name, repo_to_migrate)
                    repo_to_migrate.is_migrated = True
                    repo_to_migrate.pulp3_repository_version = repo_version
                    repo_to_migrate.save()
