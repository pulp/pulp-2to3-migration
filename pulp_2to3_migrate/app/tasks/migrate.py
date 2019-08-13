import asyncio
import importlib
import logging

from collections import namedtuple

from django.db.models import Max

from pulp_2to3_migrate.app.constants import (
    PULP_2TO3_CONTENT_MODEL_MAP,
    SUPPORTED_PULP2_PLUGINS,
)
from pulp_2to3_migrate.app.models import Pulp2Content
from pulp_2to3_migrate.pulp2 import connection

_logger = logging.getLogger(__name__)


ContentModel = namedtuple('ContentModel', ['pulp2', 'pulp_2to3_detail'])


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

    # MongoDB connection initialization
    connection.initialize()

    # TODO: Migration Plan parsing and validation
    # For now, the list of plugins to migrate is hard-coded.
    plugins_to_migrate = ['iso']

    # import all pulp 2 content models
    # (for each content type: one works with mongo and other - with postrgresql)
    content_models = []
    for plugin, model_names in SUPPORTED_PULP2_PLUGINS.items():
        if plugin not in plugins_to_migrate:
            continue
        pulp2_module_path = 'pulp_2to3_migrate.app.plugin.{plugin}.pulp2.models'.format(
            plugin=plugin)
        pulp2_module = importlib.import_module(pulp2_module_path)
        pulp_2to3_module = importlib.import_module('pulp_2to3_migrate.app.models')
        for pulp2_content_model_name in model_names:
            # mongodb model
            pulp2_content_model = getattr(pulp2_module, pulp2_content_model_name)

            # postgresql model
            content_type = pulp2_content_model.type
            pulp_2to3_detail_model_name = PULP_2TO3_CONTENT_MODEL_MAP[content_type]
            pulp_2to3_detail_model = getattr(pulp_2to3_module, pulp_2to3_detail_model_name)

            content_models.append(ContentModel(pulp2=pulp2_content_model,
                                               pulp_2to3_detail=pulp_2to3_detail_model))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(migrate_content(content_models))
    # loop.run_until_complete(migrate_repositories())
    loop.close()


async def migrate_content(content_models):
    """
    A coroutine to initiate content migration for each plugin.

    Args:
         content_models: List of Pulp 2 content models to migrate data for
    """
    pre_migrators = []
    content_migrators = []
    for content_model in content_models:
        pre_migrators.append(pre_migrate_content(content_model))

    _logger.debug('Pre-migrating Pulp 2 content')
    await asyncio.wait(pre_migrators)

    # schedule content migration into Pulp 3 using pre-migrated Pulp 2 content
    for content_model in content_models:
        content_migrators.append(content_model.pulp_2to3_detail.migrate_content_to_pulp3())

    await asyncio.wait(content_migrators)


async def pre_migrate_content(content_model):
    """
    A coroutine to pre-migrate Pulp 2 content.

    Args:
        content_model: Models for content which is being migrated.
    """
    batch_size = 10000
    content_type = content_model.pulp2.type
    pulp2content = []

    # the latest timestamp we have in the migration tool Pulp2Content table for this content type
    content_qs = Pulp2Content.objects.filter(pulp2_content_type_id=content_type)
    last_updated = content_qs.aggregate(Max('pulp2_last_updated'))['pulp2_last_updated__max'] or 0
    _logger.debug('The latest migrated {type} content has {timestamp} timestamp.'.format(
        type=content_type,
        timestamp=last_updated))

    # query only newly created/updated items
    mongo_content_qs = content_model.pulp2.objects(_last_updated__gte=last_updated)
    total_content = mongo_content_qs.count()
    _logger.debug('Total count for {type} content to migrate: {total}'.format(
        type=content_type,
        total=total_content))

    for i, record in enumerate(mongo_content_qs.only('id',
                                                     '_storage_path',
                                                     '_last_updated',
                                                     '_content_type_id',
                                                     'downloaded').batch_size(batch_size)):
        if record['_last_updated'] == last_updated:
            # corner case - content with the last``last_updated`` date might be pre-migrated;
            # check if this content is already pre-migrated
            migrated = Pulp2Content.objects.filter(pulp2_last_updated=last_updated,
                                                   pulp2_id=record['id'])
            if migrated:
                continue

        item = Pulp2Content(pulp2_id=record['id'],
                            pulp2_content_type_id=record['_content_type_id'],
                            pulp2_last_updated=record['_last_updated'],
                            pulp2_storage_path=record['_storage_path'],
                            downloaded=record['downloaded'])
        _logger.debug('Add content item to the list to migrate: {item}'.format(item=item))
        pulp2content.append(item)

        save_batch = (i and not (i + 1) % batch_size or i == total_content - 1)
        if save_batch:
            _logger.debug('Bulk save for generic content info, saved so far: {index}'.format(
                index=i + 1))
            pulp2content_batch = Pulp2Content.objects.bulk_create(pulp2content,
                                                                  ignore_conflicts=True)
            await content_model.pulp_2to3_detail.pre_migrate_content_detail(pulp2content_batch)
            pulp2content = []
