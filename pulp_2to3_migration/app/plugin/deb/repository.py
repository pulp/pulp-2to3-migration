from pulp_deb.app.models import (
    AptDistribution,
    AptPublication,
    AptRemote,
)

from pulp_deb.app.tasks.publishing import publish

from pulp_2to3_migration.app.plugin.api import (
    is_different_relative_url,
    Pulp2to3Distributor,
    Pulp2to3Importer,
)


class DebImporter(Pulp2to3Importer):
    """
    Interface to migrate Pulp 2 Deb importer.
    """
    pulp3_remote_models = [AptRemote]

    @classmethod
    def migrate_to_pulp3(cls, pulp2importer):
        """
        Migrate importer to Pulp 3.

        Args:
            pulp2importer(Pulp2Importer): Pre-migrated pulp2 importer to migrate.

        Return:
            remote(AptRemote): AptRemote in Pulp3.
            created(bool): True if Remote has just been created; False if Remote is an existing one.
        """
        pulp2_config = pulp2importer.pulp2_config
        base_config, name = cls.parse_base_config(pulp2importer, pulp2_config)
        base_config['name'] = name
        base_config['distributions'] = pulp2_config.get('releases').replace(',', ' ')
        base_config['components'] = pulp2_config.get('components').replace(',', ' ')
        base_config['architectures'] = pulp2_config.get('architectures').replace(',', ' ')
        return AptRemote.objects.update_or_create(**base_config)


class DebDistributor(Pulp2to3Distributor):
    """
    Interface to migrate Pulp 2 Deb distributor.
    """
    pulp3_publication_models = [AptPublication]
    pulp3_distribution_models = [AptDistribution]

    @classmethod
    def migrate_to_pulp3(cls, pulp2distributor, repo_version):
        """
        Migrate distributor to Pulp 3.

        Args:
            pulp2distributor(Pulp2ditributor): Pre-migrated pulp2 distributor to migrate

        Return:
            publication(AptPublication): publication in Pulp3
            distribution(AptDistribution): distribution in Pulp3
            created(bool): True if Distribution has just been created;
                           False if Distribution is an existing one;
        """
        # this will go away with the simple-complex plan conversion work
        if not repo_version:
            repo = pulp2distributor.pulp2_repos.filter(not_in_plan=False, is_migrated=True)
            repo_version = repo[0].pulp3_repository_version
        publication = repo_version.publication_set.first()
        if not publication:
            # create publication
            publish(repo_version.pk, simple=True)
            publication = repo_version.publication_set.first()

        # create distribution
        pulp2_config = pulp2distributor.pulp2_config
        distribution_data = cls.parse_base_config(pulp2distributor, pulp2_config)
        base_path = pulp2_config.get('relative_url', pulp2distributor.pulp2_repo_id)
        distribution_data['base_path'] = base_path.rstrip('/')
        distribution_data['publication'] = publication
        distribution, created = AptDistribution.objects.update_or_create(
            name=distribution_data['name'],
            base_path=distribution_data['base_path'],
            defaults=distribution_data,
        )

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
