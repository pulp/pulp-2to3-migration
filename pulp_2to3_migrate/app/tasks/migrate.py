import asyncio
import importlib
import logging

from collections import namedtuple

from pulp_2to3_migrate.app.constants import (
    PULP_2TO3_CONTENT_MODEL_MAP,
    SUPPORTED_PULP2_PLUGINS,
)
from pulp_2to3_migrate.app.pre_migration import pre_migrate_all_without_content
from pulp_2to3_migrate.app.migration import (
    migrate_content,
    migrate_importers,
    migrate_repositories,
)
from pulp_2to3_migrate.app.models import MigrationPlan
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

    # import all pulp 2 content models
    # (for each content type: one works with mongo and other - with postgresql)
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
    loop.run_until_complete(pre_migrate_all_without_content(plan))
    loop.run_until_complete(migrate_repositories())
    loop.run_until_complete(migrate_importers(plugins_to_migrate))
    loop.run_until_complete(migrate_content(content_models))  # without RemoteArtifacts yet
#    loop.run_until_complete(create_repo_versions())
#    loop.run_until_complete(migrate_distributors(plugins_to_migrate))
    loop.close()
