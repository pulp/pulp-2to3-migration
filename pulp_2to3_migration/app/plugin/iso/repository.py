from pulp_2to3_migration.app.plugin.api import (
    is_different_relative_url,
    Pulp2to3Importer,
    Pulp2to3Distributor
)

from pulp_file.app.models import FileRemote, FilePublication, FileDistribution
from pulp_file.manifest import Manifest
from pulp_file.app.tasks.publishing import populate

from django.core.files import File

from pulpcore.plugin.models import PublishedMetadata


class IsoImporter(Pulp2to3Importer):
    """
    Interface to migrate Pulp 2 ISO importer
    """
    pulp3_remote_models = [FileRemote]

    @classmethod
    def migrate_to_pulp3(cls, pulp2importer):
        """
        Migrate importer to Pulp 3.

        Args:
            pulp2importer(Pulp2Importer): Pre-migrated pulp2 importer to migrate

        Return:
            remote(FileRemote): FileRemote in Pulp3
            created(bool): True if Remote has just been created; False if Remote is an existing one
        """
        pulp2_config = pulp2importer.pulp2_config
        base_config, name = cls.parse_base_config(pulp2importer, pulp2_config)
        return FileRemote.objects.update_or_create(name=name, defaults=base_config)


class IsoDistributor(Pulp2to3Distributor):
    """
    Interface to migrate Pulp 2 ISO distributor
    """
    pulp3_publication_models = [FilePublication]
    pulp3_distribution_models = [FileDistribution]

    @classmethod
    def migrate_to_pulp3(cls, pulp2distributor, repo_version):
        """
        Migrate distributor to Pulp 3.

        Args:
            pulp2distributor(Pulp2ditributor): Pre-migrated pulp2 distributor to migrate

        Return:
            publication and distribution: FilePublication and FileDistribution in Pulp3
            created(bool): True if Distribution has just been created; False if Distribution
                           is an existing one
        """

        if not repo_version:
            repo_version = pulp2distributor.pulp2_repository.pulp3_repository_version
        publication = repo_version.publication_set.first()
        if not publication:
            # create publication
            with FilePublication.create(repo_version, pass_through=True) as publication:
                manifest = Manifest('PULP_MANIFEST')
                manifest.write(populate(publication))
                PublishedMetadata.create_from_file(
                    file=File(open(manifest.relative_path, "rb")), publication=publication
                )
        # create distribution
        pulp2_config = pulp2distributor.pulp2_config
        base_config = cls.parse_base_config(pulp2distributor, pulp2_config)
        base_config['base_path'] = pulp2_config.get('relative_url', pulp2distributor.pulp2_repo_id)
        base_config['publication'] = publication
        distribution, created = FileDistribution.objects.update_or_create(
            name=base_config['name'],
            base_path=base_config['base_path'],
            defaults=base_config)

        return publication, distribution, created

    @classmethod
    def needs_new_publication(cls, pulp2distributor):
        """
        Check if a publication associated with the pre_migrated distributor needs to be recreated.

        Nothing in a Pulp 2 distributor configuration can cause a Pulp3 publication to change.

        Args:
            pulp2distributor(Pulp2Distributor): Pre-migrated pulp2 distributor to check

        Return:
            bool: True, if a publication needs to be recreated; False if no changes are needed
        """
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
