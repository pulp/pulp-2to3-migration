import os
import unittest

from pulp_2to3_migration.tests.functional.util import set_pulp2_snapshot

from .common_plans import RPM_SIMPLE_PLAN, RPM_COMPLEX_PLAN
from .constants import FIXTURES_BASE_URL
from .rpm_base import BaseTestRpm

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


class BaseTestRpmRepo(BaseTestRpm):
    """
    Test RPM repo, importer and distributor migration.
    """
    @classmethod
    def setUpClass(cls):
        """
        Create all the client instances needed to communicate with Pulp and run a migration.
        """
        super().setUpClass()

        set_pulp2_snapshot(name='rpm_base_4repos')
        cls.run_migration(cls.plan_initial)

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


@unittest.skip('empty repos are not migrated until https://pulp.plan.io/issues/6516 is done')
class TestRpmRepoMigrationSimplePlan(BaseTestRpmRepo, unittest.TestCase):
    """
    Test RPM repo migration using simple migration plan.
    """
    plan_initial = RPM_SIMPLE_PLAN


class TestRpmRepoMigrationComplexPlan(BaseTestRpmRepo, unittest.TestCase):
    """
    Test RPM repo migration using complex migration plan.
    """
    plan_initial = RPM_COMPLEX_PLAN
