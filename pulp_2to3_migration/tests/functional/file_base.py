import time

from pulpcore.client.pulpcore import Configuration
from pulpcore.client.pulp_file import (
    ApiClient as FileApiClient,
    ContentFilesApi,
    DistributionsFileApi,
    PublicationsFileApi,
    RemotesFileApi,
    RepositoriesFileApi,
    RepositoriesFileVersionsApi,
)
from pulpcore.client.pulp_2to3_migration import (
    ApiClient as MigrationApiClient,
    MigrationPlansApi,
    Pulp2ContentApi,
    Pulp2RepositoriesApi,
)

from pulp_2to3_migration.tests.functional.util import get_psql_smash_cmd

from pulp_smash import cli
from pulp_smash import config as smash_config
from pulp_smash.pulp3.bindings import monitor_task, monitor_task_group

from .constants import BINDINGS_CONFIGURATION, TRUNCATE_TABLES_QUERY_BASH


class BaseTestFile:
    """
    Test ISO migration.
    """
    smash_cfg = smash_config.get_config()
    smash_cli_client = cli.Client(smash_cfg)

    @classmethod
    def setUpClass(cls):
        """
        Create all the client instances needed to communicate with Pulp.
        """
        configuration = Configuration(**BINDINGS_CONFIGURATION)

        file_client = FileApiClient(configuration)
        migration_client = MigrationApiClient(configuration)

        # Create api clients for all resource types
        cls.file_repo_api = RepositoriesFileApi(file_client)
        cls.file_repo_versions_api = RepositoriesFileVersionsApi(file_client)
        cls.file_remote_api = RemotesFileApi(file_client)
        cls.file_distribution_api = DistributionsFileApi(file_client)
        cls.file_publication_api = PublicationsFileApi(file_client)
        cls.file_content_api = ContentFilesApi(file_client)
        cls.migration_plans_api = MigrationPlansApi(migration_client)
        cls.pulp2content_api = Pulp2ContentApi(migration_client)
        cls.pulp2repositories_api = Pulp2RepositoriesApi(migration_client)

    @classmethod
    def run_migration(cls, plan, run_params={}):
        """
        Run a migration plan.

        Args:
            plan(str): A migration plan to run, in JSON format.
            run_params(dict): parameters for the `run` call. Optional.

        Returns:
            task(pulpcore.app.models.Task): a migration task created for this plan

        """
        mp = cls.migration_plans_api.create({'plan': plan})
        mp_run_response = cls.migration_plans_api.run(mp.pulp_href, run_params)
        task = monitor_task(mp_run_response.task)
        monitor_task_group(task.task_group)
        return task

    @classmethod
    def tearDownClass(cls):
        """
        Clean up the database after the set of tests is run.
        """
        cmd = get_psql_smash_cmd(TRUNCATE_TABLES_QUERY_BASH)
        cls.smash_cli_client.run(cmd, sudo=True)
        time.sleep(0.5)
