from pulp_2to3_migration.app.plugin.api import Pulp2to3Importer, Pulp2to3Distributor

from pulp_container.app.models import ContainerRemote, ContainerDistribution


class DockerImporter(Pulp2to3Importer):
    """
    Interface to migrate Pulp 2 Docker importer
    """
    pulp3_remote_models = [ContainerRemote]

    @classmethod
    async def migrate_to_pulp3(cls, pulp2importer):
        """
        Migrate importer to Pulp 3.

        Args:
            pulp2importer(Pulp2Importer): Pre-migrated pulp2 importer to migrate

        Return:
            remote(ContainerRemote): ContainerRemote in Pulp3
            created(bool): True if Remote has just been created; False if Remote is an existing one
        """
        pulp2_config = pulp2importer.pulp2_config
        base_config = cls.parse_base_config(pulp2importer, pulp2_config)
        # what to do if there is no upstream name?
        base_config['upstream_name'] = pulp2_config.get('upstream_name', '')
        base_config['whitelist_tags'] = pulp2_config.get('tags')
        return ContainerRemote.objects.update_or_create(**base_config)


class DockerDistributor(Pulp2to3Distributor):
    """
    Interface to migrate Pulp 2 Docker distributor
    """
    pulp3_distribution_models = [ContainerDistribution]

    @classmethod
    async def migrate_to_pulp3(cls, pulp2distributor, repo_version):
        """
        Migrate distributor to Pulp 3.

        Args:
            pulp2distributor(Pulp2Distributor): Pre-migrated pulp2 distributor to migrate

        Return:
            distribution(ContainerDistribution): ContainerDistribution in Pulp3
            created(bool): True if Distribution has just been created;
                           False if Distribution is an existing one
        """
        if not repo_version:
            repo_version = pulp2distributor.pulp2_repository.pulp3_repository_version
        pulp2_config = pulp2distributor.pulp2_config
        base_config = cls.parse_base_config(pulp2distributor, pulp2_config)
        base_config['base_path'] = pulp2_config.get(
            'repo-registry-id', pulp2distributor.pulp2_repo_id)
        base_config['repository_version'] = repo_version
        distribution, created = ContainerDistribution.objects.update_or_create(**base_config)
        return None, distribution, created
