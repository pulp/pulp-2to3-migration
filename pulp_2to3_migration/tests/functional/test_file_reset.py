import time
import unittest

from pulpcore.client.pulpcore import Configuration
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
from pulp_2to3_migration.tests.functional.util import get_psql_smash_cmd, set_pulp2_snapshot
from pulpcore.client.pulp_2to3_migration.exceptions import ApiException

from pulp_smash import cli
from pulp_smash import config as smash_config
from pulp_smash.pulp3.bindings import monitor_task, monitor_task_group

from .common_plans import FILE_SIMPLE_PLAN, RPM_SIMPLE_PLAN
from .constants import BINDINGS_CONFIGURATION, TRUNCATE_TABLES_QUERY_BASH

PULP_2_ISO_FIXTURE_DATA = {
    'repositories': 4,
    'content': 266,
}


class TestMigrationPlanReset(unittest.TestCase):
    """Test the reset functionality for a Migration Plan."""

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
        cls.file_content_api = ContentFilesApi(file_client)
        cls.migration_plans_api = MigrationPlansApi(migration_client)
        cls.pulp2content_api = Pulp2ContentApi(migration_client)
        cls.pulp2repositories_api = Pulp2RepositoriesApi(migration_client)

        set_pulp2_snapshot(name='file_base_4repos')

    def tearDown(self):
        """
        Clean up the database after each test.
        """
        cmd = get_psql_smash_cmd(TRUNCATE_TABLES_QUERY_BASH)
        self.smash_cli_client.run(cmd, sudo=True)
        time.sleep(0.5)

    def _run_migration(self, migration_plan):
        """Run a migration task and wait for it to be complete."""
        mp_run_response = self.migration_plans_api.run(migration_plan.pulp_href, {})
        task = monitor_task(mp_run_response.task)
        monitor_task_group(task.task_group)

    def _reset_pulp3_data(self, migration_plan):
        """Run a reset task and wait for it to be complete."""
        mp_run_response = self.migration_plans_api.reset(migration_plan.pulp_href, {})
        monitor_task(mp_run_response.task)

    def test_reset_file_plugin(self):
        """Test that Pulp 3 data and pre-migration data is removed for a specified plugin."""
        mp = self.migration_plans_api.create({'plan': FILE_SIMPLE_PLAN})

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
        mp_file = self.migration_plans_api.create({'plan': FILE_SIMPLE_PLAN})
        mp_rpm = self.migration_plans_api.create({'plan': RPM_SIMPLE_PLAN})

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
        mp = self.migration_plans_api.create({'plan': FILE_SIMPLE_PLAN})

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

    def test_run_only_one_reset(self):
        """Test that only one reset can be run at a time."""
        mp = self.migration_plans_api.create({'plan': FILE_SIMPLE_PLAN})

        # run twice
        mp_run_response = self.migration_plans_api.reset(mp.pulp_href, {})
        with self.assertRaises(ApiException):
            self.migration_plans_api.reset(mp.pulp_href, {})

        # make sure the first task is completed not to interfere with further tests
        monitor_task(mp_run_response.task)

    def test_no_reset_when_migration(self):
        """Test that reset is not run when migration is."""
        mp = self.migration_plans_api.create({'plan': FILE_SIMPLE_PLAN})

        # run the migration plan and then immediately run reset without waiting
        mp_run_response = self.migration_plans_api.run(mp.pulp_href, {})
        with self.assertRaises(ApiException):
            self.migration_plans_api.reset(mp.pulp_href, {})

        # make sure the first task is completed not to interfere with further tests
        task = monitor_task(mp_run_response.task)
        monitor_task_group(task.task_group)
