import asyncio

from pulp_2to3_migration.app.plugin.api import (
    ContentMigrationFirstStage,
    DeclarativeContentMigration,
    Pulp2to3PluginMigrator,
)

from pulp_file.app.models import FileRepository

from .pulp2_models import ISO
from .pulp_2to3_models import Pulp2ISO
from .repository import IsoImporter, IsoDistributor


class IsoMigrator(Pulp2to3PluginMigrator):
    """
    An entry point for migration the Pulp 2 ISO plugin to Pulp 3.

    Attributes:
        pulp2_plugin(str): Pulp 2 plugin name
        pulp2_content_models(dict): {'pulp2 content_type_id': 'content class to access MongoDB'}
        pulp2_collection(str): a pulp2 collection which existence signifies that a plugin
                               is installed in pulp2
        pulp3_plugin(str): Pulp 3 plugin name
        content_models(dict): {'pulp2 content_type_id': 'detail content class to pre-migrate to'}
        importer_migrators(dict): {'importer_type_id': 'pulp_2to3 importer interface/migrator'}

    """
    pulp2_plugin = 'iso'
    pulp2_content_models = {
        'iso': ISO,
    }
    pulp2_collection = 'units_iso'
    pulp3_plugin = 'pulp_file'
    pulp3_repository = FileRepository
    content_models = {
        'iso': Pulp2ISO,
    }
    importer_migrators = {
        'iso_importer': IsoImporter,
    }
    distributor_migrators = {
        'iso_distributor': IsoDistributor,
    }
    lazy_types = {
        'iso': Pulp2ISO,
    }

    @classmethod
    def migrate_content_to_pulp3(cls, skip_corrupted=False):
        """
        Migrate pre-migrated Pulp 2 ISO content.

        Args:
            skip_corrupted (bool): If True, corrupted content is skipped during migration,
                                   no task failure.

        """
        first_stage = ContentMigrationFirstStage(cls, skip_corrupted=skip_corrupted)
        dm = DeclarativeContentMigration(first_stage=first_stage)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(dm.create())
