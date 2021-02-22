import json
import time
import unittest

from .common_plans import FILE_COMPLEX_PLAN, FILE_DISTRIBUTOR_DIFF_PLAN, FILE_IMPORTER_DIFF_PLAN
from .constants import FILE_MANY_URL, FILE_URL, TRUNCATE_TABLES_QUERY_BASH
from .file_base import BaseTestFile
from .util import get_psql_smash_cmd, set_pulp2_snapshot


FILE_2DISTRIBUTORS_PLAN = json.dumps({  # 2 distributors for the file repo, and one - for file2.
    "plugins": [{
        "type": "iso",
        "repositories": [
            {
                "name": "file",
                "pulp2_importer_repository_id": "file",  # policy: immediate
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file",  # content count: iso - 3
                        "pulp2_distributor_repository_ids": ["file", "file-many"]
                    }
                ]
            },
            {
                "name": "file2",
                "pulp2_importer_repository_id": "file2",  # policy: on_demand
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file2",  # content count: iso - 3
                        "pulp2_distributor_repository_ids": ["file2"]
                    }
                ]
            },
        ]
    }]
})

FILE_2DISTRIBUTORS_MOVED_PLAN = json.dumps({  # now a distributor moved from file repo to file2 one.
    "plugins": [{
        "type": "iso",
        "repositories": [
            {
                "name": "file",
                "pulp2_importer_repository_id": "file",  # policy: immediate
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file",  # content count: iso - 3
                        "pulp2_distributor_repository_ids": ["file"]
                    }
                ]
            },
            {
                "name": "file2",
                "pulp2_importer_repository_id": "file2",  # policy: on_demand
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file2",  # content count: iso - 3
                        "pulp2_distributor_repository_ids": ["file2", "file-many"]
                    }
                ]
            },
        ]
    }]
})


class TestMigrationPlanChanges(BaseTestFile, unittest.TestCase):
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

    def test_importer_swap(self):
        """
        Test that if only importers in migration plan changed, the changes are noticed.

        Importers themselves haven't changed in Pulp 2, only where they are specified in the
        Migration Plan.
        """
        # run for the first time with the standard plan
        self.run_migration(FILE_COMPLEX_PLAN)
        pulp2repo_file_1run = self.pulp2repositories_api.list(pulp2_repo_id='file').results[0]
        pulp2repo_filemany_1run = self.pulp2repositories_api.list(
            pulp2_repo_id='file-many').results[0]
        pulp3_remote_file_1run = self.file_remote_api.read(pulp2repo_file_1run.pulp3_remote_href)
        pulp3_remote_filemany_1run = self.file_remote_api.read(
            pulp2repo_filemany_1run.pulp3_remote_href
        )

        # run a plan with swapped importers
        self.run_migration(FILE_IMPORTER_DIFF_PLAN)
        pulp2repo_file_2run = self.pulp2repositories_api.list(pulp2_repo_id='file').results[0]
        pulp2repo_filemany_2run = self.pulp2repositories_api.list(
            pulp2_repo_id='file-many').results[0]
        pulp3_remote_file_2run = self.file_remote_api.read(pulp2repo_file_2run.pulp3_remote_href)
        pulp3_remote_filemany_2run = self.file_remote_api.read(
            pulp2repo_filemany_2run.pulp3_remote_href
        )

        self.assertEqual(pulp3_remote_file_1run.url, FILE_URL)
        self.assertEqual(pulp3_remote_filemany_1run.url, FILE_MANY_URL)
        self.assertEqual(pulp3_remote_file_1run, pulp3_remote_filemany_2run)
        self.assertEqual(pulp3_remote_filemany_1run, pulp3_remote_file_2run)

    def test_distributor_swap(self):
        """
        Test that if only distributors in migration plan changed, the changes are noticed.

        Distributors themselves haven't changed in Pulp 2, only where they are specified in the
        Migration Plan.
        """
        # run for the first time with the standard plan
        self.run_migration(FILE_COMPLEX_PLAN)
        pulp2repo_file_1run = self.pulp2repositories_api.list(pulp2_repo_id='file').results[0]
        pulp2repo_filemany_1run = self.pulp2repositories_api.list(
            pulp2_repo_id='file-many').results[0]
        pulp3_pub_file_1run = self.file_publication_api.read(
            pulp2repo_file_1run.pulp3_publication_href
        )
        pulp3_dist_file_1run = self.file_distribution_api.read(
            pulp2repo_file_1run.pulp3_distribution_hrefs[0]
        )
        pulp3_pub_filemany_1run = self.file_publication_api.read(
            pulp2repo_filemany_1run.pulp3_publication_href
        )
        pulp3_dist_filemany_1run = self.file_distribution_api.read(
            pulp2repo_filemany_1run.pulp3_distribution_hrefs[0]
        )

        # run a plan with swapped distributors
        self.run_migration(FILE_DISTRIBUTOR_DIFF_PLAN)
        pulp2repo_file_2run = self.pulp2repositories_api.list(pulp2_repo_id='file').results[0]
        pulp2repo_filemany_2run = self.pulp2repositories_api.list(
            pulp2_repo_id='file-many').results[0]
        pulp3_pub_file_2run = self.file_publication_api.read(
            pulp2repo_file_2run.pulp3_publication_href
        )
        pulp3_dist_file_2run = self.file_distribution_api.read(
            pulp2repo_file_2run.pulp3_distribution_hrefs[0]
        )
        pulp3_pub_filemany_2run = self.file_publication_api.read(
            pulp2repo_filemany_2run.pulp3_publication_href
        )
        pulp3_dist_filemany_2run = self.file_distribution_api.read(
            pulp2repo_filemany_2run.pulp3_distribution_hrefs[0]
        )

        self.assertEqual(pulp3_dist_file_1run.base_path, 'file')
        self.assertEqual(pulp3_dist_filemany_1run.base_path, 'file-many')
        self.assertEqual(pulp3_dist_file_1run.base_path, pulp3_dist_filemany_2run.base_path)
        self.assertEqual(pulp3_dist_filemany_1run.base_path, pulp3_dist_file_2run.base_path)

        # No publications should be re-used
        self.assertNotEqual(pulp3_pub_file_1run, pulp3_pub_file_2run)
        self.assertNotEqual(pulp3_pub_filemany_1run, pulp3_pub_filemany_2run)
        self.assertNotEqual(pulp3_pub_file_1run, pulp3_pub_filemany_2run)
        self.assertNotEqual(pulp3_pub_filemany_1run, pulp3_pub_file_2run)

        # No distributions should be re-used
        self.assertNotEqual(pulp3_dist_file_1run, pulp3_dist_file_2run)
        self.assertNotEqual(pulp3_dist_filemany_1run, pulp3_dist_filemany_2run)
        self.assertNotEqual(pulp3_dist_file_1run, pulp3_dist_filemany_2run)
        self.assertNotEqual(pulp3_dist_filemany_1run, pulp3_dist_file_2run)

    def test_distributor_move(self):
        """Test when a distributor moved from one repo to another in the migration plan."""
        # run for the first time with the plan for 2 distributors in one repo
        self.run_migration(FILE_2DISTRIBUTORS_PLAN)
        pulp2repo_file = self.pulp2repositories_api.list(pulp2_repo_id='file').results[0]
        pulp2repo_file2 = self.pulp2repositories_api.list(pulp2_repo_id='file2').results[0]

        pulp3_file_dist_base_paths_1run = []
        pulp3_file2_dist_base_paths_1run = []
        for dist_href in pulp2repo_file.pulp3_distribution_hrefs:
            base_path = self.file_distribution_api.read(dist_href).base_path
            pulp3_file_dist_base_paths_1run.append(base_path)
        for dist_href in pulp2repo_file2.pulp3_distribution_hrefs:
            base_path = self.file_distribution_api.read(dist_href).base_path
            pulp3_file2_dist_base_paths_1run.append(base_path)

        # run a plan with one distributor moved to another repo in the plan
        self.run_migration(FILE_2DISTRIBUTORS_MOVED_PLAN)
        pulp2repo_file = self.pulp2repositories_api.list(pulp2_repo_id='file').results[0]
        pulp2repo_file2 = self.pulp2repositories_api.list(pulp2_repo_id='file2').results[0]

        pulp3_file_dist_base_paths_2run = []
        pulp3_file2_dist_base_paths_2run = []
        for dist_href in pulp2repo_file.pulp3_distribution_hrefs:
            base_path = self.file_distribution_api.read(dist_href).base_path
            pulp3_file_dist_base_paths_2run.append(base_path)
        for dist_href in pulp2repo_file2.pulp3_distribution_hrefs:
            base_path = self.file_distribution_api.read(dist_href).base_path
            pulp3_file2_dist_base_paths_2run.append(base_path)

        self.assertEqual(len(pulp3_file_dist_base_paths_1run), 2)
        self.assertEqual(len(pulp3_file2_dist_base_paths_1run), 1)
        self.assertEqual(len(pulp3_file_dist_base_paths_2run), 1)
        self.assertEqual(len(pulp3_file2_dist_base_paths_2run), 2)

        self.assertIn('file', pulp3_file_dist_base_paths_1run)
        self.assertIn('file-many', pulp3_file_dist_base_paths_1run)
        self.assertIn('file2', pulp3_file2_dist_base_paths_1run)
        self.assertIn('file', pulp3_file_dist_base_paths_2run)
        self.assertIn('file2', pulp3_file2_dist_base_paths_2run)
        self.assertIn('file-many', pulp3_file2_dist_base_paths_2run)
