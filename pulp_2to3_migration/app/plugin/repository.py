from urllib.parse import urlparse

from pulp_2to3_migration.app.constants import PULP_2TO3_POLICIES


class Pulp2to3Importer:
    """
    Pulp 2to3 importer migration interface.

    Plugins should subclass it and define `migrate_to_pulp3` method.

    Attributes:
        pulp3_remote_models(list): a list of models for Remotes which plugin supports

    """
    pulp3_remote_models = []

    class Meta:
        abstract = True

    @staticmethod
    def parse_base_config(pulp2importer, pulp2_config):
        """
        Parse and return basic config.
        """
        base_config = {}
        proxy_url, credentials, host = None, None, None
        pulp2_proxy_host = pulp2_config.get('proxy_host')
        pulp2_proxy_port = pulp2_config.get('proxy_port')
        pulp2_proxy_username = pulp2_config.get('proxy_username')
        pulp2_proxy_password = pulp2_config.get('proxy_password')
        if pulp2_proxy_username:
            credentials = '{}:{}'.format(pulp2_proxy_username, pulp2_proxy_password)
        if pulp2_proxy_host:
            parsed_url = urlparse(pulp2_proxy_host)
            scheme = parsed_url.scheme
            host = parsed_url.hostname
            if pulp2_proxy_port:
                host += ':{}'.format(pulp2_proxy_port)
            if credentials:
                proxy_url = '{}://{}@{}'.format(scheme, credentials, host)
            else:
                proxy_url = '{}://{}'.format(scheme, host)
        remote_name = '{}-{}'.format(pulp2importer.pulp2_object_id,
                                     pulp2importer.pulp2_repo_id)
        base_config['proxy_url'] = proxy_url
        base_config['url'] = pulp2_config.get('feed', '')  # what to do if there is no feed?
        base_config['ca_cert'] = pulp2_config.get('ssl_ca_cert')
        base_config['client_cert'] = pulp2_config.get('ssl_client_cert')
        base_config['client_key'] = pulp2_config.get('ssl_client_key')
        # True by default?
        base_config['tls_validation'] = pulp2_config.get('ssl_validation', True)
        base_config['username'] = pulp2_config.get('basic_auth_username')
        base_config['password'] = pulp2_config.get('basic_auth_password')
        base_config['download_concurrency'] = pulp2_config.get('max_downloads') or 20
        policy = PULP_2TO3_POLICIES.get(pulp2_config.get('download_policy', 'immediate'))
        base_config['policy'] = policy
        return base_config, remote_name

    @classmethod
    def migrate_to_pulp3(cls, pulp2importer):
        """
        Migrate pre-migrated Pulp 2 importer.

        Args:
            pulp2importer(Pulp2Importer): Pre-migrated pulp2 importer to migrate

        Return:
            remote(Remote): Corresponding plugin Remote in Pulp3
            created(bool): True if Remote has just been created; False if Remote is an existing one

        """
        raise NotImplementedError()


class Pulp2to3Distributor:
    """
    Pulp 2to3 distributor migration interface.

    Plugins should subclass it and define `migrate_to_pulp3` method.

    Attributes:
        pulp3_publication_models(list): a list of models for Publications which plugin supports
        pulp3_distribution_models(list): a list of models for Distributions which plugin supports

    """
    pulp3_publication_models = []
    pulp3_distribution_models = []

    class Meta:
        abstract = True

    @staticmethod
    def parse_base_config(pulp2distributor, pulp2_config):
        """
        Parse and return basic config.
        """
        base_config = {}
        name = '{}-{}'.format(pulp2distributor.pulp2_object_id,
                              pulp2distributor.pulp2_repo_id)
        base_config['name'] = name
        return base_config

    @classmethod
    def migrate_to_pulp3(cls, pulp2distributor, repo_version):
        """
        Migrate pre-migrated Pulp 2 distributor.

        Args:
            pulp2distributor(Pulp2Distributor): Pre-migrated pulp2 distributor to migrate

        Return:
            publication/distribution: Corresponding plugin's object in Pulp3
            created(bool): True if distribution has just been created;
                           False if distribution is an existing one

        """
        raise NotImplementedError()

    @classmethod
    def needs_new_publication(cls, pulp2distributor):
        """
        Check if a publication associated with the pre_migrated distributor needs to be recreated.

        Some plugins don't have publications at all, they can always return False.
        It's not done by default, because if a plugin has publications, it needs to implement
        this method properly. Only plugin knows which configuration of Pulp 2 distributor might
        affect a Pulp 3 publication.

        Args:
            pulp2distributor(Pulp2Distributor): Pre-migrated pulp2 distributor to check

        Return:
            bool: True, if a publication needs to be recreated; False if no changes are needed
        """
        raise NotImplementedError()

    @classmethod
    def needs_new_distribution(cls, pulp2distributor):
        """
        Check if a distribution associated with the pre_migrated distributor needs to be recreated.

        Only plugin knows which configuration of Pulp 2 distributor might affect a Pulp 3
        distribution.

        Args:
            pulp2distributor(Pulp2Distributor): Pre-migrated pulp2 distributor to check

        Return:
            bool: True, if a distribution needs to be recreated; False if no changes are needed

        """
        raise NotImplementedError()


def is_different_relative_url(pulp2distributor):
    """
    Check if a distribution associated with the pre_migrated distributor has the same relative url.

    Args:
        pulp2distributor(Pulp2Distributor): Pre-migrated pulp2 distributor to check

    Return:
        bool: True, if a relative url is different; False otherwise

    """
    if not pulp2distributor.pulp3_distribution:
        return True

    new_base_path = pulp2distributor.pulp2_config.get('relative_url',
                                                      pulp2distributor.pulp2_repo_id)
    current_base_path = pulp2distributor.pulp3_distribution.base_path
    if new_base_path != current_base_path:
        return True

    return False
