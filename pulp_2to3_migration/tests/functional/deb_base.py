import time

from pulpcore.client.pulpcore import Configuration
from pulpcore.client.pulp_deb import (
    ApiClient as DebApiClient,
    ContentPackageReleaseComponentsApi,
    ContentPackagesApi,
    ContentReleaseArchitecturesApi,
    ContentReleaseComponentsApi,
    ContentReleasesApi,
    DistributionsAptApi,
    PublicationsAptApi,
    RemotesAptApi,
    RepositoriesAptApi,
    RepositoriesDebVersionsApi,
)
from pulpcore.client.pulp_2to3_migration import (
    ApiClient as MigrationApiClient,
    MigrationPlansApi,
    Pulp2ContentApi,
    Pulp2RepositoriesApi,
)

from pulp_2to3_migration.tests.functional.util import get_psql_smash_cmd

from pulp_smash import cli
from pulp_smash import config as smash_config
from pulp_smash.pulp3.bindings import monitor_task, monitor_task_group

from .constants import BINDINGS_CONFIGURATION, TRUNCATE_TABLES_QUERY_BASH


class BaseTestDeb:
    """
    Test DEB migration re-runs.
    """

    smash_cfg = smash_config.get_config()
    smash_cli_client = cli.Client(smash_cfg)
    plan_initial = None
    plan_rerun = None

    @classmethod
    def setUpClass(cls):
        """
        Create all the client instances needed to communicate with Pulp.
        """
        configuration = Configuration(**BINDINGS_CONFIGURATION)

        deb_client = DebApiClient(configuration)
        migration_client = MigrationApiClient(configuration)

        # Create api clients for all resource types
        cls.deb_repo_api = RepositoriesAptApi(deb_client)
        cls.deb_repo_versions_api = RepositoriesDebVersionsApi(deb_client)
        cls.deb_remote_api = RemotesAptApi(deb_client)
        cls.deb_distribution_api = DistributionsAptApi(deb_client)
        cls.deb_publication_api = PublicationsAptApi(deb_client)
        cls.deb_content_apis = {
            "package": ContentPackagesApi(deb_client),
            "architecture": ContentReleaseArchitecturesApi(deb_client),
            "component": ContentReleaseComponentsApi(deb_client),
            "release": ContentReleasesApi(deb_client),
            "package_component": ContentPackageReleaseComponentsApi(deb_client),
        }
        cls.migration_plans_api = MigrationPlansApi(migration_client)
        cls.pulp2content_api = Pulp2ContentApi(migration_client)
        cls.pulp2repositories_api = Pulp2RepositoriesApi(migration_client)

    @classmethod
    def run_migration(cls, plan, run_params={}):
        """
        Run a migration plan.

        Args:
            plan(str): A migration plan to run, in JSON format.
            run_params(dict): parameters for the `run` call. Optional.

        Returns:
            task(pulpcore.app.models.Task): a migration task created for this plan

        """
        mp = cls.migration_plans_api.create({"plan": plan})
        mp_run_response = cls.migration_plans_api.run(mp.pulp_href, run_params)
        task = monitor_task(mp_run_response.task)
        monitor_task_group(task.task_group)
        return task

    @classmethod
    def tearDownClass(cls):
        """
        Clean up the database after the set of tests is run.
        """
        cmd = get_psql_smash_cmd(TRUNCATE_TABLES_QUERY_BASH)
        cls.smash_cli_client.run(cmd, sudo=True)
        time.sleep(0.5)


class RepoInfo(dict):
    """
    Wrapper object for repo information dict.

    Calculates expectations properly depending on whether a simple migration plan is used, or not.
    """

    def __init__(self, *args, is_simple=False, **kwargs):
        """Init.

        Args:
            is_simple (bool): Whether the expectations should be for a simple or complex plan.
        """
        super().__init__(*args, **kwargs)
        self.is_simple = is_simple

    @property
    def repositories(self):
        """Return dictionaries of content counts."""
        repositories = self.get("content_rerun", None) or self["content_initial"]
        if self.is_simple:
            return {k: v for k, v in repositories.items() if v}
        else:
            return repositories

    @property
    def new_repositories(self):
        """Return the dictionaries for new repositories only."""
        repos = []
        for repo_name, new_content in self["content_rerun"].items():
            if self.is_simple:
                initial_content = self["content_initial"].get(repo_name, None)
                if not initial_content and new_content:
                    repos.append(repo_name)
            else:
                if repo_name not in self["content_initial"]:
                    repos.append(repo_name)
        return repos

    @property
    def content_total(self):
        """Return content count dictionary."""
        # we can't just sum up the content counts because the same content could be in
        # multiple repos
        return self["content_total"]

    @property
    def remotes(self):
        """Return the count of remotes."""
        # for complex plans, you can use one remote for many repos, so we can't assume
        # the number of repos == the number of repositories
        return self["remotes"]

    @property
    def publications(self):
        """Return the count of publications."""
        return len(self.repositories)

    @property
    def distributions(self):
        """Return the count of distributions."""
        return len(self.repositories)
