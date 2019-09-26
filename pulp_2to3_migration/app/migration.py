import asyncio
import hashlib
import logging

from pulpcore.plugin.models import (
    ProgressReport,
    Repository,
)

from pulp_2to3_migration.app.models import (
    Pulp2Content,
    Pulp2Importer,
    Pulp2Repository,
)
from pulp_2to3_migration.app.plugin import PLUGIN_MIGRATORS

_logger = logging.getLogger(__name__)


async def migrate_content(plugins_to_migrate):
    """
    A coroutine to initiate content migration for each plugin.

    Args:
         plugins_to_migrate(list): List of plugins to migrate
    """
    content_migration_coros = []

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


async def migrate_repositories():
    """
    A coroutine to migrate pre-migrated repositories.
    """
    progress_data = dict(
        message='Creating repositories in Pulp 3', code='creating.repositories', total=0
    )
    with ProgressReport(**progress_data) as pb:
        pulp2repos_qs = Pulp2Repository.objects.filter(pulp3_repository_version=None)
        pb.total += pulp2repos_qs.count()
        pb.save()

        for pulp2repo in pulp2repos_qs:
            # if pulp2 repo_id is too long, its hash is included in pulp3 repo name
            pulp3_repo_name = pulp2repo.pulp2_repo_id
            if len(pulp3_repo_name) > 255:
                repo_name_hash = hashlib.sha256(pulp3_repo_name.encode()).hexdigest()
                pulp3_repo_name = '{}-{}'.format(pulp3_repo_name[:190], repo_name_hash)

            repo, created = Repository.objects.get_or_create(
                name=pulp3_repo_name,
                description=pulp2repo.pulp2_description)
            if created:
                pb.increment()
            else:
                pb.total -= 1
                pb.save()


async def migrate_importers(plugins_to_migrate):
    """
    A coroutine to migrate pre-migrated importers.

    Args:
        plugins_to_migrate(list): A list of plugins which are being migrated.
    """
    # gather all needed plugin importer migrators
    importer_migrators = {}
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
