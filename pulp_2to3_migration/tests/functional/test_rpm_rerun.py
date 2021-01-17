import json
import unittest

from collections import defaultdict

from pulp_2to3_migration.tests.functional.util import set_pulp2_snapshot

from .common_plans import INITIAL_REPOSITORIES, RPM_SIMPLE_PLAN, RPM_COMPLEX_PLAN
from .rpm_base import BaseTestRpm, RepoInfo


RERUN_REPOSITORIES = INITIAL_REPOSITORIES + [
    {
        "name": "rpm-richnweak-deps",
        "pulp2_importer_repository_id": "rpm-richnweak-deps",  # policy: on_demand
        "repository_versions": [
            {
                "pulp2_repository_id": "rpm-richnweak-deps",
                "pulp2_distributor_repository_ids": ["rpm-richnweak-deps"]
            }
        ]
    }
]

RPM_RERUN_PLAN = json.dumps({
    "plugins": [{
        "type": "rpm",
        "repositories": RERUN_REPOSITORIES
    }]
})

PULP_2_RPM_DATA = {
    'remotes': 4,
    'content_initial': {
        'rpm-empty': {},
        'rpm-empty-for-copy': {},
        'rpm-with-modules': {
            'advisory': 6,
            'modulemd': 10,
            'modulemd-defaults': 3,
            'category': 1,
            'group': 2,
            'langpack': 1,
            'package': 34,
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
    'content_rerun': {
        'rpm-empty': {},
        'rpm-empty-for-copy': {
            'package': 1
        },
        'rpm-with-modules': {
            'advisory': 6,
            'modulemd': 10,
            'modulemd-defaults': 3,
            'category': 1,
            'group': 2,
            'langpack': 1,
            'package': 34,
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
        'rpm-richnweak-deps': {
            'package': 14,
        },
    },
    'content_total': {
        'package': 53,
        'advisory': 8,
        'modulemd': 10,
        'modulemd-defaults': 3,
        'disttree': 1,
        'environment': 1,
        'category': 3,
        'group': 5,
        'langpack': 3,
    },
    'content_added': 15,
    'versions': {
        'rpm-empty': 1,
        'rpm-empty-for-copy': 2,
        'rpm-with-modules': 3,
        'rpm-distribution-tree': 2,
        'srpm-unsigned': 2,
        'rpm-richnweak-deps': 2

    },
    'new_remotes': 2,
    'new_publications': 4,
    'new_distributions': 5,
}


class BaseTestRpmRerun(BaseTestRpm):
    """
    Test RPM migration re-runs.
    """
    @classmethod
    def setUpClass(cls):
        """
        Create all the client instances needed to communicate with Pulp and run migrations.
        """
        super().setUpClass()

        def collect_migration_data():
            """Collect data from a migration run to use later for comparison."""
            data = {
                'repos': defaultdict(dict),
                'remotes': defaultdict(dict),
                'publications': defaultdict(dict),
                'distributions': defaultdict(dict),
            }
            for repo in cls.rpm_repo_api.list().results:
                latest_version = cls.rpm_repo_versions_api.read(repo.latest_version_href)
                data['repos'][repo.name] = {
                    'created': repo.pulp_created,
                    'latest_version_number': latest_version.number,
                    'latest_version_created': latest_version.pulp_created,
                }
            for remote in cls.rpm_remote_api.list().results:
                data['remotes'][remote.name] = {
                    'created': remote.pulp_created
                }
            for pub in cls.rpm_publication_api.list().results:
                data['publications'][pub.repository] = {
                    'created': pub.pulp_created
                }
            for dist in cls.rpm_distribution_api.list().results:
                data['distributions'][dist.name] = {
                    'created': dist.pulp_created
                }
            return data

        set_pulp2_snapshot(name='rpm_base_4repos')
        cls.task_initial = cls.run_migration(cls.plan_initial)
        cls.first_migration_data = collect_migration_data()

        set_pulp2_snapshot(name='rpm_base_4repos_rerun_changes')
        cls.task_rerun = cls.run_migration(cls.plan_rerun)

    def test_rpm_only_added_content(self):
        """
        Test that only newly added content is migrated on a rerun and not all.

        And that all old one stays as is as well.
        """
        content_added = 0
        for pr in self.task_rerun.progress_reports:
            if pr.code == 'migrating.content':
                content_added = pr.done
                break
        self.assertEqual(content_added, self.repo_info['content_added'])

        # content count in total
        for content_type, api in self.rpm_content_apis.items():
            with self.subTest(content_type=content_type):
                self.assertEqual(api.list().count, self.repo_info.content_total[content_type])

    def test_rpm_only_added_or_changed_repos(self):
        """
        Test that only newly added or changed repos are migrated on a rerun and not all.

        Compare timestamps from initial run. And make sure repos are migrated correctly.
        """
        self.assertEqual(self.rpm_repo_api.list().count, len(self.repo_info.repositories))
        new_repo_count = 0
        for repo in self.rpm_repo_api.list().results:
            with self.subTest(repo=repo):
                if repo.name in self.first_migration_data['repos']:
                    repo_data = self.first_migration_data['repos'][repo.name]
                    repo_version = self.rpm_repo_versions_api.list(
                        repo.pulp_href, number=repo_data['latest_version_number']
                    ).results[0]
                    self.assertEqual(repo.pulp_created, repo_data['created'])
                    self.assertEqual(repo_version.pulp_created, repo_data['latest_version_created'])
                else:
                    new_repo_count += 1

                repo_versions = self.rpm_repo_versions_api.list(repo.pulp_href)
                self.assertEqual(repo_versions.count, self.repo_info['versions'][repo.name])

                # content count per repo
                for content_type, api in self.rpm_content_apis.items():
                    with self.subTest(content_type=content_type):
                        repo_content = api.list(repository_version=repo.latest_version_href)
                        self.assertEqual(
                            repo_content.count,
                            self.repo_info.repositories[repo.name].get(content_type, 0)
                        )
        self.assertEqual(new_repo_count, len(self.repo_info.new_repositories))

    def test_rpm_importers_only_added_or_with_changed_config(self):
        """
        Test that only newly added or importers which feed changed are migrated on a rerun.

        The only changed feed is for the 'rpm-with-modules' repo.
        """
        REPO_FEED_CHANGE = 'rpm-with-modules'
        self.assertEqual(self.rpm_remote_api.list().count, self.repo_info['remotes'])
        new_remote_count = 0
        for remote in self.rpm_remote_api.list().results:
            with self.subTest(remote=remote):
                if remote.name in self.first_migration_data['remotes']:
                    remote_data = self.first_migration_data['remotes'][remote.name]
                    repo_name = '-'.join(remote.name.split('-')[1:])
                    if repo_name == REPO_FEED_CHANGE:
                        self.assertNotEqual(remote.pulp_created, remote_data['created'])
                        new_remote_count += 1
                    else:
                        self.assertEqual(remote.pulp_created, remote_data['created'])
                else:
                    new_remote_count += 1

        self.assertEqual(new_remote_count, self.repo_info['new_remotes'])

    def test_rpm_distributors_only_added_or_with_changed_config(self):
        """
        Test that only newly added or changed distributors are migrated on a rerun.

        New content in a repo forces to recreate publications and distributors.
        A change in checksum type forces to recreate publications and distributors.
        A change in relative_url/base_path forces to recreate distributors.
        """
        REPO_NEW_CONTENT = 'rpm-empty-for-copy'
        REPO_REMOVED_CONTENT = 'rpm-with-modules'
        REPO_CHECKSUMTYPE_CHANGE = 'rpm-distribution-tree'
        REPO_BASE_PATH_CHANGE = 'srpm-unsigned'
        CHANGED_PUB_REPOS = (REPO_NEW_CONTENT, REPO_REMOVED_CONTENT, REPO_CHECKSUMTYPE_CHANGE)
        CHANGED_DIST_REPOS = (
            REPO_NEW_CONTENT, REPO_REMOVED_CONTENT, REPO_CHECKSUMTYPE_CHANGE, REPO_BASE_PATH_CHANGE
        )
        self.assertEqual(self.rpm_publication_api.list().count, self.repo_info.publications)
        self.assertEqual(self.rpm_distribution_api.list().count, self.repo_info.distributions)
        new_publication_count = 0
        for pub in self.rpm_publication_api.list().results:
            with self.subTest(pub=pub):
                if pub.repository in self.first_migration_data['publications']:
                    pub_data = self.first_migration_data['publications'][pub.repository]
                    repo_name = self.rpm_repo_api.read(pub.repository).name
                    if repo_name in CHANGED_PUB_REPOS:
                        self.assertNotEqual(pub.pulp_created, pub_data['created'])
                        new_publication_count += 1
                    else:
                        self.assertEqual(pub.pulp_created, pub_data['created'])
                else:
                    new_publication_count += 1

        self.assertEqual(new_publication_count, self.repo_info['new_publications'])

        new_distribution_count = 0
        for dist in self.rpm_distribution_api.list().results:
            with self.subTest(dist=dist):
                if dist.name in self.first_migration_data['distributions']:
                    dist_data = self.first_migration_data['distributions'][dist.name]
                    repo_name = '-'.join(dist.name.split('-')[1:])
                    if repo_name in CHANGED_DIST_REPOS:
                        self.assertNotEqual(dist.pulp_created, dist_data['created'])
                        new_distribution_count += 1
                    else:
                        self.assertEqual(dist.pulp_created, dist_data['created'])
                else:
                    new_distribution_count += 1

        self.assertEqual(new_distribution_count, self.repo_info['new_distributions'])


class TestRpmRerunSimplePlan(BaseTestRpmRerun, unittest.TestCase):
    """
    Test RPM repo migration using simple migration plan.
    """
    plan_initial = RPM_SIMPLE_PLAN
    plan_rerun = RPM_SIMPLE_PLAN
    repo_info = RepoInfo(PULP_2_RPM_DATA, is_simple=True)


class TestRpmRerunComplexPlan(BaseTestRpmRerun, unittest.TestCase):
    """
    Test RPM repo migration using complex migration plan.
    """
    plan_initial = RPM_COMPLEX_PLAN
    plan_rerun = RPM_RERUN_PLAN
    repo_info = RepoInfo(PULP_2_RPM_DATA)
