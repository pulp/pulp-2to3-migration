import asyncio

from pulpcore.plugin.stages import (
    ArtifactSaver,
    ContentSaver,
    QueryExistingArtifacts,
    QueryExistingContents,
    ResolveContentFutures,
)

from pulp_deb.app import models as pulp3_models

from pulp_2to3_migration.app.plugin.api import (
    ContentMigrationFirstStage,
    DeclarativeContentMigration,
    Pulp2to3PluginMigrator,
    RelatePulp2to3Content,
)

from . import (
    pulp2_models,
    pulp_2to3_models,
    repository,
)


class DebMigrator(Pulp2to3PluginMigrator):
    """
    An entry point for migration the Pulp 2 Debian plugin to Pulp 3.

    Attributes:
      Check parent class.

    """
    pulp2_plugin = 'deb'
    pulp2_content_models = {
        'deb': pulp2_models.DebPackage,
    }
    pulp2_collection = 'units_deb'
    pulp3_plugin = 'pulp_deb'
    pulp3_repository = pulp3_models.AptRepository
    content_models = {
        'deb': pulp_2to3_models.Pulp2DebPackage,
    }
    importer_migrators = {
        'deb_importer': repository.DebImporter,
    }
    distributor_migrators = {
        'deb_distributor': repository.DebDistributor,
    }
    future_types = {
        'deb': pulp_2to3_models.Pulp2DebPackage,
    }

    @classmethod
    def migrate_content_to_pulp3(cls, skip_corrupted=False):
        """
        Migrate pre-migrated Pulp 2 Debian content.

        Args:
            skip_corrupted (bool): If True, corrupted content is skipped during migration,
                                   no task failure.

        """
        first_stage = ContentMigrationFirstStage(cls, skip_corrupted=skip_corrupted)
        dm = DebDeclarativeContentMigration(first_stage=first_stage)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(dm.create())


class DebDeclarativeContentMigration(DeclarativeContentMigration):
    """
    A pipeline that migrates pre-migrated Pulp 2 deb content into Pulp 3.
    """

    def pipeline_stages(self):
        """
        Build a list of stages.

        This defines the "architecture" of the content migration to Pulp 3.

        Returns:
            list: List of :class:`~pulpcore.plugin.stages.Stage` instances.

        """
        pipeline = [
            self.first_stage,
            QueryExistingArtifacts(),
            ArtifactSaver(),
            QueryExistingContents(),
            ContentSaver(),
            ResolveContentFutures(),
            RelatePulp2to3Content(),
        ]

        return pipeline
