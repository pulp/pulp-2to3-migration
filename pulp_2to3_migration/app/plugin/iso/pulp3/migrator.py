from pulp_2to3_migration.app.plugin.api import (
    ContentMigrationFirstStage,
    DeclarativeContentMigration,
    Pulp2to3PluginMigrator,
)

from .models import Pulp2ISO


class IsoMigrator(Pulp2to3PluginMigrator):
    """
    An entry point for migration the Pulp 2 ISO plugin to Pulp 3.
    """
    type = 'iso'
    content_models = (Pulp2ISO,)

    @classmethod
    async def migrate_content_to_pulp3(cls):
        """
        Migrate pre-migrated Pulp 2 ISO content.
        """
        first_stage = ContentMigrationFirstStage(cls)
        dm = DeclarativeContentMigration(first_stage=first_stage)
        await dm.create()
