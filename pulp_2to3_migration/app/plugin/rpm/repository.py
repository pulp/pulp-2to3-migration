from pulp_2to3_migration.app.plugin.api import (
    Pulp2to3Importer,
#    Pulp2to3Distributor
)

from pulp_rpm.app.models import (
    RpmRemote,
#    RpmPublication,
#    RpmDistribution
)


class RpmImporter(Pulp2to3Importer):
    """
    Interface to migrate Pulp 2 RPM importer
    """
    pulp3_remote_models = [RpmRemote]

    @classmethod
    async def migrate_to_pulp3(cls, pulp2importer):
        """
        Migrate importer to Pulp 3.

        Args:
            pulp2importer(Pulp2Importer): Pre-migrated pulp2 importer to migrate

        Return:
            remote(RpmRemote): RpmRemote in Pulp3
            created(bool): True if Remote has just been created; False if Remote is an existing one
        """
        pulp2_config = pulp2importer.pulp2_config
        base_config = cls.parse_base_config(pulp2importer, pulp2_config)
        return RpmRemote.objects.update_or_create(**base_config)
