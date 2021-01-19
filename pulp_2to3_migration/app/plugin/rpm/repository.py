from pulp_2to3_migration.app.plugin.api import (
    is_different_relative_url,
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
    def migrate_to_pulp3(cls, pulp2importer):
        """
        Migrate importer to Pulp 3.

        Args:
            pulp2importer(Pulp2Importer): Pre-migrated pulp2 importer to migrate

        Return:
            remote(RpmRemote): RpmRemote in Pulp3
            created(bool): True if Remote has just been created; False if Remote is an existing one
        """
        pulp2_config = pulp2importer.pulp2_config
        base_config, name = cls.parse_base_config(pulp2importer, pulp2_config)
        sles_auth_token = pulp2_config.get('query_auth_token')
        if sles_auth_token:
            base_config['sles_auth_token'] = sles_auth_token
        return RpmRemote.objects.update_or_create(name=name, defaults=base_config)


class RpmDistributor(Pulp2to3Distributor):
    """
    Interface to migrate Pulp 2 RPM distributor
    """
    pulp3_publication_models = [RpmPublication]
    pulp3_distribution_models = [RpmDistribution]

    @classmethod
    def migrate_to_pulp3(cls, pulp2distributor, repo_version):
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
        pulp2_config = pulp2distributor.pulp2_config

        # this will go away with the simple-complex plan conversion work
        if not repo_version:
            repo = pulp2distributor.pulp2_repos.filter(not_in_plan=False, is_migrated=True)
            repo_version = repo[0].pulp3_repository_version
        publication = repo_version.publication_set.first()
        if not publication:
            pulp2_checksum_type = pulp2_config.get('checksum_type')
            checksum_types = None
            if pulp2_checksum_type:
                checksum_types = {'metadata': pulp2_checksum_type,
                                  'package': pulp2_checksum_type}
            sqlite = pulp2_config.get('generate_sqlite', False)
            try:
                publish(repo_version.pk, checksum_types=checksum_types, sqlite_metadata=sqlite)
            except TypeError:
                # hack, pulp_rpm <3.9 doesn't support sqlite_metadata kwarg
                publish(repo_version.pk, checksum_types=checksum_types)
            publication = repo_version.publication_set.first()

        # create distribution
        distribution_data = cls.parse_base_config(pulp2distributor, pulp2_config)

        # ensure that the base_path does not end with / in Pulp 3, it's often present in Pulp 2.
        base_path = pulp2_config.get('relative_url', pulp2distributor.pulp2_repo_id)
        distribution_data['base_path'] = base_path.rstrip('/')
        distribution_data['publication'] = publication
        distribution, created = RpmDistribution.objects.update_or_create(
            name=distribution_data['name'],
            base_path=distribution_data['base_path'],
            defaults=distribution_data)
        return publication, distribution, created

    @classmethod
    def needs_new_publication(cls, pulp2distributor):
        """
        Check if a publication associated with the pre_migrated distributor needs to be recreated.

        Args:
            pulp2distributor(Pulp2Distributor): Pre-migrated pulp2 distributor to check

        Return:
            bool: True, if a publication needs to be recreated; False if no changes are needed

        """
        new_checksum_type = pulp2distributor.pulp2_config.get('checksum_type')
        current_checksum_type = pulp2distributor.pulp3_publication.cast().metadata_checksum_type

        is_default_checksum_type = new_checksum_type is None and current_checksum_type == 'sha256'
        if new_checksum_type != current_checksum_type and not is_default_checksum_type:
            return True

        return False

    @classmethod
    def needs_new_distribution(cls, pulp2distributor):
        """
        Check if a distribution associated with the pre_migrated distributor needs to be recreated.

        Args:
            pulp2distributor(Pulp2Distributor): Pre-migrated pulp2 distributor to check

        Return:
            bool: True, if a distribution needs to be recreated; False if no changes are needed

        """
        return is_different_relative_url(pulp2distributor)
