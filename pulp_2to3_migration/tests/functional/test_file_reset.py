import json
import unittest

from pulpcore.client.pulpcore import (
    ApiClient as CoreApiClient,
    Configuration,
    TasksApi
)
from pulpcore.client.pulp_file import (
    ApiClient as FileApiClient,
    ContentFilesApi,
    RepositoriesFileApi,
)
from pulpcore.client.pulp_2to3_migration import (
    ApiClient as MigrationApiClient,
    MigrationPlansApi,
    Pulp2ContentApi,
    Pulp2RepositoriesApi,
)
from pulp_2to3_migration.tests.functional.util import (
    get_psql_smash_cmd,
    monitor_task
)

from pulp_smash import cli
from pulp_smash import config as smash_config

from .constants import TRUNCATE_TABLES_QUERY_BASH

PULP_2_ISO_FIXTURE_DATA = {
    'repositories': 4,
    'content': 266,
}

EMPTY_ISO_MIGRATION_PLAN = json.dumps({"plugins": [{"type": "iso"}]})
EMPTY_RPM_MIGRATION_PLAN = json.dumps({"plugins": [{"type": "rpm"}]})


class TestMigrationPlanReset(unittest.TestCase):
    """Test the reset functionality for a Migration Plan."""

    smash_cfg = smash_config.get_config()
    smash_cli_client = cli.Client(smash_cfg)

    @classmethod
    def setUpClass(cls):
        """
        Create all the client instances needed to communicate with Pulp.
        """
        configuration = Configuration()
        configuration.username = 'admin'
        configuration.password = 'password'
        configuration.host = 'http://pulp'
        configuration.safe_chars_for_path_param = '/'

        core_client = CoreApiClient(configuration)
        file_client = FileApiClient(configuration)
        migration_client = MigrationApiClient(configuration)

        # Create api clients for all resource types
        cls.file_repo_api = RepositoriesFileApi(file_client)
        cls.file_content_api = ContentFilesApi(file_client)
        cls.tasks_api = TasksApi(core_client)
        cls.migration_plans_api = MigrationPlansApi(migration_client)
        cls.pulp2content_api = Pulp2ContentApi(migration_client)
        cls.pulp2repositories_api = Pulp2RepositoriesApi(migration_client)

    def tearDown(self):
        """
        Clean up the database after each test
        """
        cmd = get_psql_smash_cmd(TRUNCATE_TABLES_QUERY_BASH)
        self.smash_cli_client.run(cmd, sudo=True)

    def _run_migration(self, migration_plan):
        """Run a migration task and wait for it to be complete."""
        mp_run_response = self.migration_plans_api.run(migration_plan.pulp_href, {})
        task = monitor_task(self.tasks_api, mp_run_response.task)
        self.assertEqual(task.state, "completed")

    def _reset_pulp3_data(self, migration_plan):
        """Run a reset task and wait for it to be complete."""
        mp_run_response = self.migration_plans_api.reset(migration_plan.pulp_href, {})
        task = monitor_task(self.tasks_api, mp_run_response.task)
        self.assertEqual(task.state, "completed")

    def test_reset_file_plugin(self):
        """Test that Pulp 3 data and pre-migration data is removed for a specified plugin."""
        mp = self.migration_plans_api.create({'plan': EMPTY_ISO_MIGRATION_PLAN})

        self._run_migration(mp)
        # Assert that pre-migrated data is there
        self.assertEqual(self.pulp2repositories_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['repositories'])
        self.assertEqual(self.pulp2content_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['content'])
        # Assert that Pulp 3 data is there
        self.assertEqual(self.file_repo_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['repositories'])
        self.assertEqual(self.file_content_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['content'])

        self._reset_pulp3_data(mp)
        # Assert that pre-migrated data is no longer there
        self.assertEqual(self.pulp2repositories_api.list().count, 0)
        self.assertEqual(self.pulp2content_api.list().count, 0)
        # Assert that Pulp 3 data is no longer there
        self.assertEqual(self.file_repo_api.list().count, 0)
        self.assertEqual(self.file_content_api.list().count, 0)

    def test_no_reset_plugin_data(self):
        """
        Test that no data is removed for a plugin which is not specified in a plan.

        Run migration for the File plugin.
        Reset data for the RPM plugin and ensure that nothing is deleted.
        """
        mp_file = self.migration_plans_api.create({'plan': EMPTY_ISO_MIGRATION_PLAN})
        mp_rpm = self.migration_plans_api.create({'plan': EMPTY_RPM_MIGRATION_PLAN})

        self._run_migration(mp_file)
        # Assert that pre-migrated data is there
        self.assertEqual(self.pulp2repositories_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['repositories'])
        self.assertEqual(self.pulp2content_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['content'])
        # Assert that Pulp 3 data is there
        self.assertEqual(self.file_repo_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['repositories'])
        self.assertEqual(self.file_content_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['content'])

        self._reset_pulp3_data(mp_rpm)
        # Assert that pre-migrated data is still there
        self.assertEqual(self.pulp2repositories_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['repositories'])
        self.assertEqual(self.pulp2content_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['content'])
        # Assert that Pulp 3 data is still there
        self.assertEqual(self.file_repo_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['repositories'])
        self.assertEqual(self.file_content_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['content'])

    def test_migrate_after_reset(self):
        """Test that migration runs successfully after the reset of Pulp 3 and pre-migrated data."""
        mp = self.migration_plans_api.create({'plan': EMPTY_ISO_MIGRATION_PLAN})

        self._run_migration(mp)
        # Assert that pre-migrated data is there
        self.assertEqual(self.pulp2repositories_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['repositories'])
        self.assertEqual(self.pulp2content_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['content'])
        # Assert that Pulp 3 data is there
        self.assertEqual(self.file_repo_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['repositories'])
        self.assertEqual(self.file_content_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['content'])

        self._reset_pulp3_data(mp)
        # Assert that pre-migrated data is no longer there
        self.assertEqual(self.pulp2repositories_api.list().count, 0)
        self.assertEqual(self.pulp2content_api.list().count, 0)
        # Assert that Pulp 3 data is no longer there
        self.assertEqual(self.file_repo_api.list().count, 0)
        self.assertEqual(self.file_content_api.list().count, 0)

        self._run_migration(mp)
        # Assert that pre-migrated data is back there
        self.assertEqual(self.pulp2repositories_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['repositories'])
        self.assertEqual(self.pulp2content_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['content'])
        # Assert that Pulp 3 data is back there
        self.assertEqual(self.file_repo_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['repositories'])
        self.assertEqual(self.file_content_api.list().count,
                         PULP_2_ISO_FIXTURE_DATA['content'])
