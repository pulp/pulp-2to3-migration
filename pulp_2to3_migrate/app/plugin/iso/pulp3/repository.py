from pulp_2to3_migrate.app.constants import PULP_2TO3_POLICIES
from pulp_2to3_migrate.app.plugin.api import Pulp2to3Importer

from pulp_file.app.models import FileRemote


class IsoImporter(Pulp2to3Importer):
    """
    Interface to migrate Pulp 2 ISO importer
    """
    @classmethod
    async def migrate_to_pulp3(cls, pulp2importer):
        """
        Migrate importer to Pulp 3.

        NOTE/TODO: Global pulp2/importer settings are not taking into account.

        Args:
            pulp2importer(Pulp2Importer): Pre-migrated pulp2 importer to migrate

        Return:
            remote(FileRemote): FileRemote in Pulp3
            created(bool): True if Remote has just been created; False if Remote is an existing one
        """
        pulp2_config = pulp2importer.pulp2_config
        proxy_url, credentials, host = None, None, None
        pulp2_proxy_host = pulp2_config.get('proxy_host')
        pulp2_proxy_port = pulp2_config.get('proxy_port')
        pulp2_proxy_username = pulp2_config.get('proxy_username')
        pulp2_proxy_password = pulp2_config.get('proxy_password')
        if pulp2_proxy_username:
            credentials = '{}:{}'.format(pulp2_proxy_username, pulp2_proxy_password)
        if pulp2_proxy_host:
            host = pulp2_proxy_host
            if pulp2_proxy_port:
                host += ':{}'.format(pulp2_proxy_port)
            if credentials:
                proxy_url = 'https://{}@{}'.format(credentials, host)
        remote_name = '{}-{}'.format(pulp2importer.pulp2_object_id,
                                     pulp2importer.pulp2_repository.pulp2_repo_id)
        return FileRemote.objects.update_or_create(
            name=remote_name,
            url=pulp2_config.get('feed'),  # what to do if there is no feed?
            ssl_ca_certificate=pulp2_config.get('ssl_ca_cert'),
            ssl_client_certificate=pulp2_config.get('ssl_client_cert'),
            ssl_client_key=pulp2_config.get('ssl_client_key'),
            ssl_validation=pulp2_config.get('ssl_validation', True),  # True by default?
            proxy_url=proxy_url,
            username=pulp2_config.get('basic_auth_username'),
            password=pulp2_config.get('basic_auth_password'),
            download_concurrency=pulp2_config.get('max_downloads') or 20,
            policy=PULP_2TO3_POLICIES.get(pulp2_config.get('download_policy', 'immediate')),
        )
