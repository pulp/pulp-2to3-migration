import os
import time
import unittest

from pulpcore.client.pulpcore import Configuration
from pulpcore.client.pulp_rpm import (
    ApiClient as RpmApiClient,
    ContentAdvisoriesApi,
    # ContentDistributionTreesApi,
    ContentModulemdDefaultsApi,
    ContentModulemdsApi,
    ContentPackagecategoriesApi,
    ContentPackageenvironmentsApi,
    ContentPackagegroupsApi,
    ContentPackagelangpacksApi,
    ContentPackagesApi,
    DistributionsRpmApi,
    PublicationsRpmApi,
    RemotesRpmApi,
    RepositoriesRpmApi,
    RepositoriesRpmVersionsApi,
)
from pulpcore.client.pulp_2to3_migration import (
    ApiClient as MigrationApiClient,
    MigrationPlansApi,
)
from pulp_2to3_migration.tests.functional.util import get_psql_smash_cmd, set_pulp2_snapshot

from pulp_smash import cli
from pulp_smash import config as smash_config
from pulp_smash.pulp3.bindings import monitor_task, monitor_task_group

from .common_plans import RPM_SIMPLE_PLAN, RPM_COMPLEX_PLAN
from .constants import BINDINGS_CONFIGURATION, FIXTURES_BASE_URL, TRUNCATE_TABLES_QUERY_BASH

PULP_2_RPM_DATA = {
    'repositories': 5,
    'remotes': 3,
    'publications': 5,
    'distributions': 5,
    'content': {
        'rpm-empty': {},
        'rpm-empty-for-copy': {},
        'rpm-with-modules': {
            'advisory': 6,
            'modulemd': 10,
            'modulemd-defaults': 3,
            'category': 1,
            'group': 2,
            'langpack': 1,
            'package': 35,
        },
        'rpm-distribution-tree': {
            'disttree': 1,
            'environment': 1,
            'category': 1,
            'group': 1,
            'langpack': 1,
            'package': 1,
        },
        'srpm-unsigned': {
            'advisory': 2,
            'category': 1,
            'group': 2,
            'langpack': 1,
            'package': 3,
        },
    },
    'content_total': {
        'package': 38,
        'advisory': 8,
        'modulemd': 10,
        'modulemd-defaults': 3,
        'disttree': 1,
        'environment': 1,
        'category': 3,
        'group': 5,
        'langpack': 3,
    },

}


class BaseTestRpmRepo:
    """
    Test RPM repo, importer and distributor migration.
    """
    smash_cfg = smash_config.get_config()
    smash_cli_client = cli.Client(smash_cfg)

    @classmethod
    def setUpClass(cls):
        """
        Create all the client instances needed to communicate with Pulp.
        """
        configuration = Configuration(**BINDINGS_CONFIGURATION)

        rpm_client = RpmApiClient(configuration)
        migration_client = MigrationApiClient(configuration)

        # Create api clients for all resource types
        cls.rpm_repo_api = RepositoriesRpmApi(rpm_client)
        cls.rpm_repo_versions_api = RepositoriesRpmVersionsApi(rpm_client)
        cls.rpm_remote_api = RemotesRpmApi(rpm_client)
        cls.rpm_distribution_api = DistributionsRpmApi(rpm_client)
        cls.rpm_publication_api = PublicationsRpmApi(rpm_client)
        cls.rpm_content_apis = {
            'advisory': ContentAdvisoriesApi(rpm_client),
            # skip until https://pulp.plan.io/issues/8050 is fixed
            # 'disttree': ContentDistributionTreesApi(rpm_client),
            'modulemd': ContentModulemdsApi(rpm_client),
            'modulemd-defaults': ContentModulemdDefaultsApi(rpm_client),
            'category': ContentPackagecategoriesApi(rpm_client),
            'environment': ContentPackageenvironmentsApi(rpm_client),
            'group': ContentPackagegroupsApi(rpm_client),
            'langpack': ContentPackagelangpacksApi(rpm_client),
            'package': ContentPackagesApi(rpm_client),
        }
        cls.migration_plans_api = MigrationPlansApi(migration_client)

        set_pulp2_snapshot(name='rpm_base_4repos')

        cls.run_migration()

    @classmethod
    def tearDownClass(cls):
        """
        Clean up the database after the set of tests is run.
        """
        cmd = get_psql_smash_cmd(TRUNCATE_TABLES_QUERY_BASH)
        cls.smash_cli_client.run(cmd, sudo=True)
        time.sleep(0.5)

    def test_rpm_repo_migration(self):
        """
        Test that RPM repos are correctly migrated.

        Check that names are migrated correctly and that the number of versions and content count is
        correct.
        """
        self.assertEqual(self.rpm_repo_api.list().count, PULP_2_RPM_DATA['repositories'])

        # content count in total
        for content_type, api in self.rpm_content_apis.items():
            with self.subTest(content_type=content_type):
                self.assertEqual(api.list().count, PULP_2_RPM_DATA['content_total'][content_type])

        for repo in self.rpm_repo_api.list().results:
            with self.subTest(repo=repo):
                version_count = 2 if PULP_2_RPM_DATA['content'][repo.name] else 1
                self.assertEqual(
                    self.rpm_repo_versions_api.list(repo.pulp_href).count, version_count
                )
                # content count per repo
                for content_type, api in self.rpm_content_apis.items():
                    with self.subTest(content_type=content_type):
                        repo_content = api.list(repository_version=repo.latest_version_href)
                        self.assertEqual(
                            repo_content.count,
                            PULP_2_RPM_DATA['content'][repo.name].get(content_type, 0)
                        )

    def test_rpm_importer_migration(self):
        """
        Test that RPM importers are correctly migrated.
        """
        self.assertEqual(self.rpm_remote_api.list().count, PULP_2_RPM_DATA['remotes'])
        for remote in self.rpm_remote_api.list().results:
            with self.subTest(remote=remote):
                repo_name = '-'.join(remote.name.split('-')[1:])
                repo_url = os.path.join(FIXTURES_BASE_URL, repo_name) + '/'
                self.assertEqual(remote.url, repo_url)
                self.assertEqual(remote.policy, 'on_demand')

    def test_rpm_distributor_migration(self):
        """
        Test that RPM distributors are correctly migrated.
        """
        self.assertEqual(self.rpm_publication_api.list().count, PULP_2_RPM_DATA['publications'])
        self.assertEqual(self.rpm_distribution_api.list().count, PULP_2_RPM_DATA['distributions'])
        for dist in self.rpm_distribution_api.list().results:
            with self.subTest(dist=dist):
                base_path = '-'.join(dist.name.split('-')[1:])
                self.assertEqual(dist.base_path, base_path)


class MigrationPlanMixin:
    """A mixin class for tests to run a migration using a specified plan."""
    plan = None

    @classmethod
    def run_migration(cls):
        """Run a migration using simple plan."""
        mp = cls.migration_plans_api.create({'plan': cls.plan})
        mp_run_response = cls.migration_plans_api.run(mp.pulp_href, {})
        task = monitor_task(mp_run_response.task)
        monitor_task_group(task.task_group)


@unittest.skip('empty repos are not migrated until https://pulp.plan.io/issues/6516 is done')
class TestRpmRepoMigrationSimplePlan(BaseTestRpmRepo, unittest.TestCase, MigrationPlanMixin):
    """
    Test RPM repo migration using simple migration plan.
    """
    plan = RPM_SIMPLE_PLAN


class TestRpmRepoMigrationComplexPlan(BaseTestRpmRepo, unittest.TestCase, MigrationPlanMixin):
    """
    Test RPM repo migration using complex migration plan.
    """
    plan = RPM_COMPLEX_PLAN
