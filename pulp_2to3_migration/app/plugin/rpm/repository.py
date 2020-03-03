from pulp_2to3_migration.app.plugin.api import (
    Pulp2to3Importer,
    Pulp2to3Distributor
)

from pulp_rpm.app.models import (
    RpmRemote,
    RpmPublication,
    RpmDistribution
)
from pulp_rpm.app.tasks.publishing import publish


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


class RpmDistributor(Pulp2to3Distributor):
    """
    Interface to migrate Pulp 2 RPM distributor
    """
    pulp3_publication_models = [RpmPublication]
    pulp3_distribution_models = [RpmDistribution]

    @classmethod
    async def migrate_to_pulp3(cls, pulp2distributor, repo_version):
        """
        Migrate distributor to Pulp 3.

        Args:
            pulp2distributor(Pulp2distributor): Pre-migrated pulp2 distributor to migrate

        Return:
            publication(RpmPublication): publication in Pulp 3
            distribution(RpmDistribution): distribution in Pulp 3
            created(bool): True if a distribution has just been created; False if a distribution
                           is an existing one
        """

        if not repo_version:
            repo_version = pulp2distributor.pulp2_repository.pulp3_repository_version
        publication = repo_version.publication_set.first()
        if not publication:
            # create publication
            publish(repo_version.pk)
            publication = repo_version.publication_set.first()

        # create distribution
        pulp2_config = pulp2distributor.pulp2_config
        distribution_data = cls.parse_base_config(pulp2distributor, pulp2_config)

        # ensure that the base_path does not end with / in Pulp 3, it's often present in Pulp 2.
        base_path = pulp2_config.get(
            'relative_url', pulp2distributor.pulp2_repo_id)
        distribution_data['base_path'] = base_path.rstrip('/')
        distribution_data['publication'] = publication
        distribution, created = RpmDistribution.objects.update_or_create(**distribution_data)

        return publication, distribution, created
