import os
import unittest
from pulp_2to3_migration.tests.functional.util import set_pulp2_snapshot

from .common_plans import DEB_SIMPLE_PLAN, DEB_COMPLEX_PLAN
from .constants import FIXTURES_BASE_URL
from .deb_base import BaseTestDeb, RepoInfo

PULP_2_DEB_DATA = {
    "remotes": 3,
    "content_initial": {
        "debian-empty": {},
        "debian": {
            "package": 4,
            "package_component": 4,
            "component": 2,
            "architecture": 2,
            "release": 1,
        },
        "debian-complex-dists": {
            "package": 4,
            "package_component": 4,
            "component": 2,
            "architecture": 2,
            "release": 1,
        },
        "debian_update": {
            "package": 0,
            "package_component": 0,
            "component": 2,
            "architecture": 0,
            "release": 1,
        },
    },
    "content_total": {
        "package": 8,
        "package_component": 8,
        "component": 6,
        "architecture": 4,
        "release": 3,
    },
}


class BaseTestDebRepo(BaseTestDeb):
    """
    Test DEB repo, importer and distributor migration.
    """

    @classmethod
    def setUpClass(cls):
        """
        Create all the client instances needed to communicate with Pulp and run a migration.
        """
        super().setUpClass()

        set_pulp2_snapshot(name="deb_base_4repos")
        cls.run_migration(cls.plan_initial)

    def test_deb_repo_migration(self):
        """
        Test that DEB repos are correctly migrated.

        Check that names are migrated correctly and that the number of versions and content count is
        correct.
        """
        self.assertEqual(
            self.deb_repo_api.list().count, len(self.repo_info.repositories)
        )

        # content count in total
        for content_type, api in self.deb_content_apis.items():
            with self.subTest(content_type=content_type):
                self.assertEqual(
                    api.list().count,
                    self.repo_info.content_total[content_type],
                    "content_total[%r] does not match" % content_type,
                )

        for repo in self.deb_repo_api.list().results:
            with self.subTest(repo=repo):
                version_count = 2 if self.repo_info.repositories[repo.name] else 1
                self.assertEqual(
                    self.deb_repo_versions_api.list(repo.pulp_href).count, version_count
                )
                # content count per repo
                for content_type, api in self.deb_content_apis.items():
                    with self.subTest(content_type=content_type):
                        repo_content = api.list(
                            repository_version=repo.latest_version_href
                        )
                        self.assertEqual(
                            repo_content.count,
                            self.repo_info.repositories[repo.name].get(content_type, 0),
                            "content_type %r does not match for repo %r"
                            % (content_type, repo.name),
                        )

    def test_deb_importer_migration(self):
        """
        Test that DEB importers are correctly migrated.
        """
        self.assertEqual(self.deb_remote_api.list().count, self.repo_info.remotes)
        for remote in self.deb_remote_api.list().results:
            with self.subTest(remote=remote):
                repo_name = "-".join(remote.name.split("-")[1:])
                repo_url = os.path.join(FIXTURES_BASE_URL, repo_name) + "/"
                self.assertEqual(remote.url, repo_url)

    def test_deb_distributor_migration(self):
        """
        Test that DEB distributors are correctly migrated.
        """
        self.assertEqual(
            self.deb_publication_api.list().count, self.repo_info.publications
        )
        self.assertEqual(
            self.deb_distribution_api.list().count, self.repo_info.distributions
        )
        for dist in self.deb_distribution_api.list().results:
            with self.subTest(dist=dist):
                base_path = "-".join(dist.name.split("-")[1:])
                self.assertEqual(dist.base_path, base_path)


class TestDebRepoMigrationSimplePlan(BaseTestDebRepo, unittest.TestCase):
    """
    Test DEB repo migration using simple migration plan.
    """

    plan_initial = DEB_SIMPLE_PLAN
    repo_info = RepoInfo(PULP_2_DEB_DATA, is_simple=True)


class TestDebRepoMigrationComplexPlan(BaseTestDebRepo, unittest.TestCase):
    """
    Test DEB repo migration using complex migration plan.
    """

    plan_initial = DEB_COMPLEX_PLAN
    repo_info = RepoInfo(PULP_2_DEB_DATA)
