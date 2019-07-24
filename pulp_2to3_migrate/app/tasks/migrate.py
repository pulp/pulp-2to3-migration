import asyncio
import importlib
import logging
import time

from django.db.models import Max

from pulp_2to3_migrate.app.constants import SUPPORTED_PULP2_PLUGINS
from pulp_2to3_migrate.app.models import Pulp2Content
from pulp_2to3_migrate.pulp2 import connection

_logger = logging.getLogger(__name__)


def migrate_from_pulp2(migration_plan_pk, dry_run=False):
    """
    Main task to migrate from Pulp 2 to Pulp 3.

    Schedule other tasks based on the specified Migration Plan.

    Args:
        migration_plan_pk (str): The migration plan PK.
        dry_run (bool): If True, nothing is migrated, only validation happens.
    """
    if dry_run:
        _logger.debug('Running in a dry-run mode.')
        # TODO: Migration Plan validation
        return

    connection.initialize()

    # TODO: Migration Plan parsing and validation
    # For now, the list of plugins to migrate is hard-coded.
    plugins_to_migrate = ['iso']

    # import all pulp 2 content models
    content_models = []
    for plugin, model_names in SUPPORTED_PULP2_PLUGINS.items():
        if plugin not in plugins_to_migrate:
            continue
        module_path = 'pulp_2to3_migrate.pulp2.{plugin}.models'.format(plugin=plugin)
        module = importlib.import_module(module_path)
        for content_model_name in model_names:
            content_models.append(getattr(module, content_model_name))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(migrate_content(content_models))
    #loop.run_until_complete(migrate_repositories())
    loop.close()


async def migrate_content(content_models):
    """
    Coroutine to initiate content migration for each plugin.

    Args:
         content_models: List of Pulp 2 content models to migrate data for
    """
    migrators =[]
    for model in content_models:
        _logger.debug('Migrating generic info for {type} content'.format(type=model.type))
        migrator.append(migrate_content_generic_info(model))

    await asyncio.wait(migrators)

    # schedule content migration (hard links or copy; plugin specific content creation)


async def migrate_content_generic_info(content_model):
    """
    Coroutine to migrate generic info about any Pulp 2 content.

    Args:
        content_model: Pulp 2 model for content which is being migrated.
    """
    batch_size = 10000
    content_type = content_model.type
    pulp2_content = []

    # the latest timestamp we have in the migration tool Pulp2Content table for this content type
    content_qs = Pulp2Content.objects.filter(pulp2_content_type_id=content_type)
    last_updated = content_qs.aggregate(Max('pulp2_last_updated'))['pulp2_last_updated__max'] or 0
    _logger.debug('The latest migrated {type} content has {timestamp} timestamp.'.format(
        type=content_type,
        timestamp=last_updated))

    # query only newly created/updated items
    mongo_content_qs = content_model.objects(_last_updated__gte=last_updated)
    total_content = mongo_content_qs.count()
    _logger.debug('Total count for {type} content to migrate: {total}'.format(
        type=content_type,
        total=total_content))

    for i, record in enumerate(mongo_content_qs.only('id',
                                                     '_storage_path',
                                                     '_last_updated',
                                                     '_content_type_id',
                                                     'downloaded').batch_size(batch_size)):
        item = Pulp2Content(pulp2_id=record['id'],
                            pulp2_content_type_id=record['_content_type_id'],
                            pulp2_last_updated=record['_last_updated'],
                            pulp2_storage_path=record['_storage_path'],
                            downloaded=record['downloaded'])
        _logger.debug('Add content item to the list to migrate: {item}'.format(item=item))
        pulp2_content.append(item)

        save_batch = (i and not (i+1)%batch_size or i == total_content-1)
        if save_batch:
            _logger.debug('Bulk save for generic content info, saved so far: {index}'.format(
                index=i+1))
            Pulp2Content.objects.bulk_create(pulp2_content, ignore_conflicts=True)
            pulp2_content = []