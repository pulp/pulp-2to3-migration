from pulp_2to3_migration.app.plugin.api import Pulp2to3Importer

from pulp_docker.app.models import DockerRemote


class DockerImporter(Pulp2to3Importer):
    """
    Interface to migrate Pulp 2 Docker importer
    """

    @classmethod
    async def migrate_to_pulp3(cls, pulp2importer):
        """
        Migrate importer to Pulp 3.

        Args:
            pulp2importer(Pulp2Importer): Pre-migrated pulp2 importer to migrate

        Return:
            remote(DockerRemote): DockerRemote in Pulp3
            created(bool): True if Remote has just been created; False if Remote is an existing one
        """
        pulp2_config = pulp2importer.pulp2_config
        base_config = cls.parse_base_config(pulp2importer, pulp2_config)
        # what to do if there is no upstream name?
        base_config['upstream_name'] = pulp2_config.get('upstream_name', '')
        base_config['whitelist_tags'] = pulp2_config.get('tags')
        return DockerRemote.objects.update_or_create(**base_config)
