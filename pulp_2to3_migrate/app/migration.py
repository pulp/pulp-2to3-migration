import asyncio
import hashlib
import importlib
import logging

from pulpcore.plugin.models import (
    ProgressReport,
    Repository,
)

from pulp_2to3_migrate.app.constants import (
    PLUGIN_MIGRATORS_MAP,
    PULP_2TO3_IMPORTER_TYPE_MODEL_MAP,
)
from pulp_2to3_migrate.app.models import (
    Pulp2Content,
    Pulp2Importer,
    Pulp2Repository,
)

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
            plugin_migrator = PLUGIN_MIGRATORS_MAP.get(plugin)
            content_migration_coros.append(plugin_migrator.migrate_content_to_pulp3())

            # only used for progress bar counters
            content_types = [model.type for model in plugin_migrator.content_models]
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
    # import all needed plugin importer migration models
    importer_models = {}
    for plugin, importer_info in PULP_2TO3_IMPORTER_TYPE_MODEL_MAP.items():
        if plugin not in plugins_to_migrate:
            continue
        module_path = 'pulp_2to3_migrate.app.plugin.{plugin}.pulp3.repository'.format(plugin=plugin)
        plugin_module = importlib.import_module(module_path)
        for record in importer_info:
            importer_type_id, model_name = record
            importer_model = getattr(plugin_module, model_name)
            importer_models[importer_type_id] = importer_model

    progress_data = dict(
        message='Migrating importers to Pulp 3', code='migrating.importers', total=0
    )
    with ProgressReport(**progress_data) as pb:
        pulp2importers_qs = Pulp2Importer.objects.filter(pulp3_remote=None)
        pb.total += pulp2importers_qs.count()
        pb.save()

        for pulp2importer in pulp2importers_qs:
            importer_model = importer_models.get(pulp2importer.pulp2_type_id)
            remote, created = await importer_model.migrate_to_pulp3(pulp2importer)
            pulp2importer.pulp3_remote = remote
            pulp2importer.is_migrated = True
            pulp2importer.save()
            if created:
                pb.increment()
            else:
                pb.total -= 1
                pb.save()
