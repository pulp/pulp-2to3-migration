import json
import time
import unittest

from pulpcore.client.pulp_2to3_migration.exceptions import ApiException
from pulp_2to3_migration.tests.functional.util import get_psql_smash_cmd, set_pulp2_snapshot
from pulp_smash.pulp3.bindings import monitor_task, monitor_task_group, PulpTaskError

from .common_plans import FILE_SIMPLE_PLAN, FILE_COMPLEX_PLAN
from .constants import TRUNCATE_TABLES_QUERY_BASH
from .file_base import BaseTestFile

EXTRA_COMMA_PLAN = '{"plugins": [{"type": "iso"},]}'
MISSING_RESOURCE_PLAN = json.dumps({
    "plugins": [{
        "type": "iso",
        "repositories": [
            {
                "name": "file",
                "pulp2_importer_repository_id": "non-existing importer",  # policy: immediate
                "repository_versions": [
                    {
                        "pulp2_repository_id": "non-existing repo",  # content count: iso - 3
                        "pulp2_distributor_repository_ids": ["non-existing distributor"]
                    }
                ]
            }
        ]
    }]
})
MISSING_RESOURCE_ERROR = 'Validation failed: resources missing '\
                         '{\'repositories\': [\'non-existing repo\'], '\
                         '\'repositories_missing_importers\': [\'non-existing importer\'], '\
                         '\'repositories_missing_distributors\': [\'non-existing distributor\']}'
UNKNOWN_KEY_PLAN = json.dumps({"plugins": [{"type": "iso", "unknown key": "value"}]})


class TestMigrationPlan(BaseTestFile, unittest.TestCase):
    """Test the Migration Plan creation and validation"""

    @classmethod
    def setUpClass(cls):
        """
        Populate needed pulp2 snapshot.
        """
        super().setUpClass()
        set_pulp2_snapshot(name='file_base_4repos')

    def tearDown(self):
        """
        Clean up the database after each test.
        """
        cmd = get_psql_smash_cmd(TRUNCATE_TABLES_QUERY_BASH)
        self.smash_cli_client.run(cmd, sudo=True)
        time.sleep(0.5)

    def _do_test_parallel(self, plan, outcome):
        """Test that there were multiple tasks running in parallel as a part of a task group."""
        mp = self.migration_plans_api.create({'plan': plan})
        mp_run_response = self.migration_plans_api.run(mp.pulp_href, {})
        task = monitor_task(mp_run_response.task)
        group = monitor_task_group(task.task_group)
        self.assertEqual(group.completed, outcome)

    def test_load_simple_plan(self):
        """Test that a simple Migration Plan can be loaded and run."""
        self.run_migration(FILE_SIMPLE_PLAN)

    def test_load_complex_plan(self):
        """Test that a complex Migration Plan can be loaded and run."""
        self.run_migration(FILE_COMPLEX_PLAN)

    @unittest.skip('not fixed yet, https://pulp.plan.io/issues/7948')
    def test_load_extra_comma_plan(self):
        """Test that a proper exception is risen when there is a syntax error in a plan."""
        with self.assertRaises(ApiException) as exc:
            self.migration_plans_api.create({'plan': EXTRA_COMMA_PLAN})
            self.assertEqual(exc.code, 400)

    def test_unknown_key_plan(self):
        """Test that Migration Plan creation fails if some unknown keys are mentioned in it."""
        with self.assertRaises(ApiException) as exc:
            self.migration_plans_api.create({'plan': UNKNOWN_KEY_PLAN})
            self.assertEqual(exc.code, 400)

    def test_validate_plan(self):
        """Test that pulp 2 resources are validated."""
        self.run_migration(FILE_COMPLEX_PLAN, {'validate': True})

    def test_validate_missing_resource(self):
        """Test that pulp 2 missing resource is noticed and reported."""
        mp = self.migration_plans_api.create({'plan': MISSING_RESOURCE_PLAN})
        mp_run_response = self.migration_plans_api.run(mp.pulp_href, {'validate': True})
        with self.assertRaises(PulpTaskError) as exc:
            monitor_task(mp_run_response.task)
        self.assertEqual(exc.exception.task.error['description'], MISSING_RESOURCE_ERROR)

    def test_run_only_one_plan(self):
        """Test that only one plan can be run at a time"""
        mp = self.migration_plans_api.create({'plan': FILE_SIMPLE_PLAN})

        # run twice
        mp_run_response = self.migration_plans_api.run(mp.pulp_href, {})
        with self.assertRaises(ApiException):
            self.migration_plans_api.run(mp.pulp_href, {})

        # make sure the first task is completed not to interfere with further tests
        task = monitor_task(mp_run_response.task)
        monitor_task_group(task.task_group)

    def test_simple_plan_parallel(self):
        """Test that using a simple plan, there is work which is performed in parallel."""
        self._do_test_parallel(FILE_SIMPLE_PLAN, 5)

    def test_complex_plan_parallel(self):
        """Test that using a complex plan, there is work which is performed in parallel."""
        self._do_test_parallel(FILE_COMPLEX_PLAN, 5)

    def test_optimized_tasks_rerun(self):
        """Test that second run of the same plan with no changes at all triggers only one task"""
        self._do_test_parallel(FILE_COMPLEX_PLAN, 5)
        self._do_test_parallel(FILE_COMPLEX_PLAN, 1)
