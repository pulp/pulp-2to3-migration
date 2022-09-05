import json
import time
import unittest

from pulp_2to3_migration.tests.functional.util import (
    get_psql_smash_cmd,
    set_pulp2_snapshot,
)

from .constants import TRUNCATE_TABLES_QUERY_BASH
from .file_base import BaseTestFile

PULP_2_ISO_FIXTURE_DATA = {"file": 3, "file2": 3, "file-many": 250, "file-large": 10}

EMPTY_ISO_MIGRATION_PLAN = json.dumps({"plugins": [{"type": "iso"}]})

SPECIFIC_REPOS_MIGRATION_PLAN = json.dumps(
    {
        "plugins": [
            {
                "type": "iso",
                "repositories": [
                    {
                        "name": "file",
                        "pulp2_importer_repository_id": "file",
                        "repository_versions": [
                            {
                                "pulp2_repository_id": "file",
                                "pulp2_distributor_repository_ids": ["file"],
                            }
                        ],
                    },
                    {
                        "name": "file2",
                        "pulp2_importer_repository_id": "file2",
                        "repository_versions": [
                            {
                                "pulp2_repository_id": "file2",
                                "pulp2_distributor_repository_ids": ["file2"],
                            }
                        ],
                    },
                ],
            }
        ]
    }
)
DIFFERENT_IMPORTER_MIGRATION_PLAN = json.dumps(
    {
        "plugins": [
            {
                "type": "iso",
                "repositories": [
                    {
                        "name": "file",
                        "pulp2_importer_repository_id": "file2",
                        "repository_versions": [
                            {
                                "pulp2_repository_id": "file",
                                "pulp2_distributor_repository_ids": ["file"],
                            }
                        ],
                    },
                    {
                        "name": "file2",
                        "pulp2_importer_repository_id": "file2",
                        "repository_versions": [
                            {
                                "pulp2_repository_id": "file2",
                                "pulp2_distributor_repository_ids": ["file2"],
                            }
                        ],
                    },
                ],
            }
        ]
    }
)


# TODO:
#   - Check that distributions are created properly
#   - Check that remotes are created properly


class TestMigrationPlan(BaseTestFile, unittest.TestCase):
    """Test the APIs for creating a Migration Plan."""

    @classmethod
    def setUpClass(cls):
        """
        Populate needed pulp2 snapshot.
        """
        super().setUpClass()
        set_pulp2_snapshot(name="file_base_4repos")

    def tearDown(self):
        """
        Clean up the database after each test.
        """
        cmd = get_psql_smash_cmd(TRUNCATE_TABLES_QUERY_BASH)
        self.smash_cli_client.run(cmd, sudo=True)
        time.sleep(0.5)

    def _do_test(self, repos, migration_plan):
        self.run_migration(migration_plan, {})

        for repo_id in repos:
            pulp3repos = self.file_repo_api.list(name=repo_id)
            # Assert that there is a result
            self.failIf(
                not pulp3repos.results,
                "Missing a Pulp 3 repository for Pulp 2 " "repository id '{}'".format(repo_id),
            )
            repo_href = pulp3repos.results[0].pulp_href
            # Assert that the name in pulp 3 matches the repo_id in pulp 2
            self.assertEqual(repo_id, pulp3repos.results[0].name)
            # Assert that there is a Repository Version with the same number of content units as
            # associated with the repository in Pulp 2.
            repo_version_href = self.file_repo_versions_api.list(repo_href).results[0].pulp_href
            repo_version_content = self.file_content_api.list(repository_version=repo_version_href)
            self.assertEqual(PULP_2_ISO_FIXTURE_DATA[repo_id], repo_version_content.count)
        # TODO: count only not_in_plan=False repositories from ../pulp2repositories/ endpoint
        self.assertEqual(len(repos), self.file_repo_api.list().count)

    def test_1_migrate_specific_iso_repositories(self):
        """Test that a Migration Plan with repos specified migrates only those repos."""
        repos = list(PULP_2_ISO_FIXTURE_DATA.keys())[:2]
        self._do_test(repos, SPECIFIC_REPOS_MIGRATION_PLAN)

    def test_2_migrate_all_iso_repositories(self):
        """Test that a Migration Plan to mirror Pulp 2 executes correctly."""
        repos = list(PULP_2_ISO_FIXTURE_DATA.keys())
        self._do_test(repos, EMPTY_ISO_MIGRATION_PLAN)

    def test_3_migrate_iso_repositories_with_different_importer(self):
        """Test that a Migration Plan with different importers executes correctly."""
        repos = list(PULP_2_ISO_FIXTURE_DATA.keys())[:2]
        self._do_test(repos, DIFFERENT_IMPORTER_MIGRATION_PLAN)
