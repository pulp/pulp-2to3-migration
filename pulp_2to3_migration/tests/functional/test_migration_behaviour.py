import json
import time
import unittest

from pulpcore.client.pulpcore import Configuration

from pulpcore.client.pulp_file import (
    ApiClient as FileApiClient,
    ContentFilesApi,
    DistributionsFileApi,
    PublicationsFileApi,
    RemotesFileApi,
    RepositoriesFileApi,
    RepositoriesFileVersionsApi
)
from pulpcore.client.pulp_2to3_migration import (
    ApiClient as MigrationApiClient,
    MigrationPlansApi,
    Pulp2ContentApi,
    Pulp2RepositoriesApi
)

from pulp_2to3_migration.tests.functional.util import get_psql_smash_cmd, set_pulp2_snapshot

from pulp_smash import cli
from pulp_smash import config as smash_config
from pulp_smash.pulp3.bindings import monitor_task, monitor_task_group

from .common_plans import FILE_SIMPLE_PLAN, FILE_COMPLEX_PLAN
from .constants import BINDINGS_CONFIGURATION, FILE_MANY_URL, FILE_URL, TRUNCATE_TABLES_QUERY_BASH


MANY_INTO_ONE_PLAN = json.dumps({
    "plugins": [{
        "type": "iso",
        "repositories": [
            {
                "name": "file",
                "pulp2_importer_repository_id": "file-many",  # policy: on_demand
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file"  # content count: iso - 3
                    },
                    {
                        "pulp2_repository_id": "file-large"  # content count: iso - 10
                    },
                    {
                        "pulp2_repository_id": "file-many"  # content count: iso - 250
                    }
                ]
            }
        ]
    }]
})

IMPORTER_DIFF_PLAN = json.dumps({
    "plugins": [{
        "type": "iso",
        "repositories": [
            {
                "name": "file",
                "pulp2_importer_repository_id": "file-many",  # policy: on_demand
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file"  # content count: iso - 3
                    }
                ]
            },
            {
                "name": "file-many",
                "pulp2_importer_repository_id": "file",  # policy: immediate
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file-many"  # content count: iso - 250
                    }
                ]
            }
        ]
    }]
})

DISTRIBUTOR_DIFF_PLAN = json.dumps({
    "plugins": [{
        "type": "iso",
        "repositories": [
            {
                "name": "file",
                "pulp2_importer_repository_id": "file",  # policy: immediate
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file",  # content count: iso - 3
                        "pulp2_distributor_repository_ids": ["file-many"]
                    }
                ]
            },
            {
                "name": "file-many",
                "pulp2_importer_repository_id": "file-many",  # policy: on_demand
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file-many",  # content count: iso - 250
                        "pulp2_distributor_repository_ids": ["file"]
                    }
                ]
            }
        ]
    }]
})

IMPORTER_NO_REPO_PLAN = json.dumps({
    "plugins": [{
        "type": "iso",
        "repositories": [
            {
                "name": "file",
                "pulp2_importer_repository_id": "file-many",  # policy: on_demand
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file"  # content count: iso - 3
                    }
                ]
            }
        ]
    }]
})

DISTRIBUTOR_NO_REPO_PLAN = json.dumps({
    "plugins": [{
        "type": "iso",
        "repositories": [
            {
                "name": "file",
                "pulp2_importer_repository_id": "file",  # policy: immediate
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file",  # content count: iso - 3
                        "pulp2_distributor_repository_ids": ["file-many"]
                    }
                ]
            }
        ]
    }]
})

NO_ON_DEMAND_IMPORTER_PLAN = json.dumps({
    "plugins": [{
        "type": "iso",
        "repositories": [
            {
                "name": "file-many",
                "pulp2_importer_repository_id": "file",  # policy: immediate
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file-many",  # content count: iso - 250
                        "pulp2_distributor_repository_ids": ["file-many"]
                    }
                ]
            }
        ]
    }]
})

NO_IMMEDIATE_IMPORTER_PLAN = json.dumps({
    "plugins": [{
        "type": "iso",
        "repositories": [
            {
                "name": "file",
                "pulp2_importer_repository_id": "file-many",  # policy: on_demand
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file",  # content count: iso - 3
                        "pulp2_distributor_repository_ids": ["file"]
                    }
                ]
            }
        ]
    }]
})

CONTENT_COUNT = {
    'file': 3,
    'file2': 3,
    'file-large': 10,
    'file-many': 250
}


class TestMigrationBehaviour(unittest.TestCase):
    """Test the migration behaviour."""

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

        # Create api clients for all resource types needed
        cls.file_content_api = ContentFilesApi(file_client)
        cls.file_distributions_api = DistributionsFileApi(file_client)
        cls.file_publications_api = PublicationsFileApi(file_client)
        cls.file_remotes_api = RemotesFileApi(file_client)
        cls.file_repo_api = RepositoriesFileApi(file_client)
        cls.file_repo_versions_api = RepositoriesFileVersionsApi(file_client)
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

    def _load_and_run(self, plan, run_params={}):
        """Load and run a migration plan."""
        mp = self.migration_plans_api.create({'plan': plan})
        mp_run_response = self.migration_plans_api.run(mp.pulp_href, run_params)
        task = monitor_task(mp_run_response.task)
        # to ensure that migration fully finished and further tests won't collide with it
        monitor_task_group(task.task_group)
        return task

    def _test_pulp2content(self, plan):
        """
        Test that pulp2content/ endpoint provides an href for a migrated content.

        Check the first content in the list.
        """
        self._load_and_run(plan)
        pulp2content = self.pulp2content_api.list(ordering='pulp2_id', limit=1).results[0]
        content_href = pulp2content.pulp3_content
        file_content = self.file_content_api.read(content_href)
        self.assertEqual(file_content.relative_path, '137.iso')

    def _test_pulp2repositories(self, plan):
        """
        Test that pulp2repositories/ endpoint provides info for the migrated Pulp 2 repository.

        Check correctness of the dara for the first repo in the list.
        """
        self._load_and_run(plan)
        pulp2repository = self.pulp2repositories_api.list(
            ordering='pulp2_repo_id', limit=1
        ).results[0]
        pulp3_repo = self.file_repo_api.read(pulp2repository.pulp3_repository_href)
        pulp3_remote = self.file_remotes_api.read(pulp2repository.pulp3_remote_href)
        pulp3_pub = self.file_publications_api.read(pulp2repository.pulp3_publication_href)
        pulp3_dist = self.file_distributions_api.read(pulp2repository.pulp3_distribution_hrefs[0])

        self.assertEqual(self.pulp2repositories_api.list().count, 4)
        self.assertTrue(pulp2repository.is_migrated)
        self.assertEqual(pulp2repository.pulp2_repo_id, 'file')
        self.assertEqual(pulp3_repo.name, 'file')
        self.assertEqual(pulp3_repo.latest_version_href, pulp2repository.pulp3_repository_version)
        self.assertEqual(pulp3_remote.url, FILE_URL)
        self.assertEqual(pulp3_remote.policy, 'immediate')
        self.assertEqual(pulp3_pub.manifest, 'PULP_MANIFEST')
        self.assertEqual(pulp3_pub.repository_version, pulp2repository.pulp3_repository_version)
        self.assertEqual(pulp3_pub.distributions[0], pulp3_dist.pulp_href)
        self.assertEqual(pulp3_dist.base_path, 'file')

    def test_pulp2content_simple_plan(self):
        """Test pulp2content endpoint for a simple plan."""
        self._test_pulp2content(FILE_SIMPLE_PLAN)

    def test_pulp2content_complex_plan(self):
        """Test pulp2content endpoint for a complex plan."""
        self._test_pulp2content(FILE_COMPLEX_PLAN)

    def test_pulp2repositories_simple_plan(self):
        """Test pulp2repositories endpoint for a simple plan."""
        self._test_pulp2repositories(FILE_SIMPLE_PLAN)

    def test_pulp2repositories_complex_plan(self):
        """Test pulp2repositories endpoint for a complex plan."""
        self._test_pulp2repositories(FILE_COMPLEX_PLAN)

    def test_many_into_one_repo(self):
        """
        Test that many Pulp 2 repos can be migrated into one Pulp 3 repo.

        Each repo version behaves in "mirror" mode is case, each repo version should perfectly
        reflect the pulp 2 repo and not be additive.
        """
        self._load_and_run(MANY_INTO_ONE_PLAN)
        pulp2repositories = self.pulp2repositories_api.list().results
        pulp3_repo = self.file_repo_api.list().results[0]

        self.assertEqual(self.file_repo_api.list().count, 1)
        self.assertEqual(self.file_repo_versions_api.list(pulp3_repo.pulp_href).count, 4)
        self.assertEqual(self.file_content_api.list().count, 263)
        for pulp2repo in pulp2repositories:
            with self.subTest(pulp2repo=pulp2repo):
                self.assertTrue(pulp2repo.is_migrated)
                self.assertEqual(pulp2repo.pulp3_repository_href, pulp3_repo.pulp_href)
                repo_content = self.file_content_api.list(
                    repository_version=pulp2repo.pulp3_repository_version
                )
                self.assertEqual(repo_content.count, CONTENT_COUNT[pulp2repo.pulp2_repo_id])

    def test_importer_different_repo(self):
        """
        Test that an importer can be migrated with any Pulp 2 repo, not its native one.

        Importers are swapped in the plan.
        """
        self._load_and_run(IMPORTER_DIFF_PLAN)
        pulp2repositories = self.pulp2repositories_api.list(ordering='pulp2_repo_id').results
        pulp2repo1, pulp2repo2 = pulp2repositories
        pulp3_remote1 = self.file_remotes_api.read(pulp2repo1.pulp3_remote_href)
        pulp3_remote2 = self.file_remotes_api.read(pulp2repo2.pulp3_remote_href)

        self.assertEqual(pulp2repo1.pulp2_repo_id, 'file')
        self.assertEqual(pulp2repo2.pulp2_repo_id, 'file-many')
        self.assertTrue(pulp2repo1.is_migrated)
        self.assertTrue(pulp2repo2.is_migrated)
        self.assertEqual(pulp3_remote1.url, FILE_MANY_URL)
        self.assertEqual(pulp3_remote2.url, FILE_URL)
        self.assertEqual(pulp3_remote1.policy, 'on_demand')
        self.assertEqual(pulp3_remote2.policy, 'immediate')

    def test_distributor_different_repo(self):
        """
        Test that a distributor can be migrated with any Pulp 2 repo, not its native one.

        Distributors are swapped in the plan.
        """
        self._load_and_run(DISTRIBUTOR_DIFF_PLAN)
        pulp2repositories = self.pulp2repositories_api.list(ordering='pulp2_repo_id').results
        pulp2repo1, pulp2repo2 = pulp2repositories
        pulp3_pub1 = self.file_publications_api.read(pulp2repo1.pulp3_publication_href)
        pulp3_pub2 = self.file_publications_api.read(pulp2repo2.pulp3_publication_href)
        pulp3_dist1 = self.file_distributions_api.read(pulp2repo1.pulp3_distribution_hrefs[0])
        pulp3_dist2 = self.file_distributions_api.read(pulp2repo2.pulp3_distribution_hrefs[0])

        self.assertEqual(pulp2repo1.pulp2_repo_id, 'file')
        self.assertEqual(pulp2repo2.pulp2_repo_id, 'file-many')
        self.assertTrue(pulp2repo1.is_migrated)
        self.assertTrue(pulp2repo2.is_migrated)
        self.assertEqual(pulp3_pub1.repository_version, pulp2repo1.pulp3_repository_version)
        self.assertEqual(pulp3_pub2.repository_version, pulp2repo2.pulp3_repository_version)
        self.assertEqual(pulp3_pub1.distributions[0], pulp3_dist1.pulp_href)
        self.assertEqual(pulp3_pub2.distributions[0], pulp3_dist2.pulp_href)
        self.assertEqual(pulp3_dist1.base_path, 'file-many')
        self.assertEqual(pulp3_dist2.base_path, 'file')

    def test_importer_no_repo(self):
        """Test that an importer can be migrated without its native Pulp 2 repo."""
        self._load_and_run(IMPORTER_NO_REPO_PLAN)
        pulp2repository = self.pulp2repositories_api.list().results[0]
        pulp3_remote = self.file_remotes_api.read(pulp2repository.pulp3_remote_href)

        self.assertEqual(self.pulp2repositories_api.list().count, 1)
        self.assertEqual(self.file_remotes_api.list().count, 1)
        self.assertTrue(pulp2repository.is_migrated)
        self.assertEqual(pulp2repository.pulp2_repo_id, 'file')
        self.assertEqual(pulp3_remote.url, FILE_MANY_URL)
        self.assertEqual(pulp3_remote.policy, 'on_demand')

    def test_distributor_no_repo(self):
        """Test that a distributor can be migrated without its native Pulp 2 repo."""
        self._load_and_run(DISTRIBUTOR_NO_REPO_PLAN)
        pulp2repository = self.pulp2repositories_api.list().results[0]
        pulp3_pub = self.file_publications_api.read(pulp2repository.pulp3_publication_href)
        pulp3_dist = self.file_distributions_api.read(pulp2repository.pulp3_distribution_hrefs[0])

        self.assertEqual(self.pulp2repositories_api.list().count, 1)
        self.assertEqual(self.file_distributions_api.list().count, 1)
        self.assertTrue(pulp2repository.is_migrated)
        self.assertEqual(pulp2repository.pulp2_repo_id, 'file')
        self.assertEqual(pulp3_pub.repository_version, pulp2repository.pulp3_repository_version)
        self.assertEqual(pulp3_pub.distributions[0], pulp3_dist.pulp_href)
        self.assertEqual(pulp3_dist.base_path, 'file-many')

    def test_no_on_demand_importer(self):
        """Test that if there is no importer for on_demand content, such content is not migrated."""
        self._load_and_run(NO_ON_DEMAND_IMPORTER_PLAN)
        pulp3_repo = self.file_repo_api.list().results[0]
        repo_content = self.file_content_api.list(repository_version=pulp3_repo.latest_version_href)

        self.assertEqual(self.file_repo_versions_api.list(pulp3_repo.pulp_href).count, 1)
        self.assertEqual(repo_content.count, 0)

    def test_no_immediate_importer(self):
        """Test that if there is no importer for downloaded content, such content is migrated."""
        self._load_and_run(NO_IMMEDIATE_IMPORTER_PLAN)
        pulp3_repo = self.file_repo_api.list().results[0]
        repo_content = self.file_content_api.list(repository_version=pulp3_repo.latest_version_href)

        self.assertEqual(self.file_repo_versions_api.list(pulp3_repo.pulp_href).count, 2)
        self.assertEqual(repo_content.count, 3)
