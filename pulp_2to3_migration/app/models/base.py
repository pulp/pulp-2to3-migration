import itertools

from django.contrib.postgres.fields import JSONField

from pulpcore.plugin.models import BaseModel

from pulp_2to3_migration.pulp2 import connection
from pulp_2to3_migration.pulp2.base import (
    Distributor,
    Importer,
    Repository,
)


class MigrationPlan(BaseModel):
    """
    Migration Plans that have been created and maybe even run.

    Fields:
        plan (models.JSONField): The migration plan in the JSON format
    """
    plan = JSONField()
    _real_plan = None

    @property
    def plan_view(self):
        """
        Cached and validated migration plan.
        """
        if not self._real_plan:
            self._real_plan = _InternalMigrationPlan(self.plan)

        return self._real_plan

    def get_plugin_plans(self):
        """
        Return a list of pulp2 plugin migration plan structures.
        """
        return self.plan_view._plugin_plans

    def get_plugins(self):
        """
        Return a list of pulp2 plugin names to migrate.
        """
        return [plugin.type for plugin in self.get_plugin_plans()]

    def get_repositories(self):
        """
        Return a list of pulp2 repositories to migrate or empty list if all should be migrated.
        """
        return self.plan_view.all_repositories_to_migrate

    def get_importers(self):
        """
        Pulp2 repositories to migrate importers for or empty list if all should be migrated.
        """
        return self.plan_view.all_repositories_importers_to_migrate

    def get_distributors(self):
        """
        Pulp2 repositories to migrate distributors for or empty list if all should be migrated.
        """
        return self.plan_view.all_repositories_distributors_to_migrate

    def get_pulp3_repository_setup(self):
        """
        Return a dict of pulp3 repositories to create and information about e.g. versions.
        """
        # return {
        #     plan.type: plan.repositories_to_create
        #     for plan in self.plan_view.get_plugin_plans()
        # }

        ret = {}
        for plan in self.plugin_plans():
            ret.update(plan.repositories_to_create)
        return ret

    def get_missing_resources(self):
        """
        Return a dict of any resources listed in the plan but missing from Pulp 2.

        Repositories and Importers are enumerated by repo_id, Distributors by distributor_id.
        """
        ret = {}
        if self.plan_view.missing_repositories:
            ret['repositories'] = self.plan_view.missing_repositories
        if self.plan_view.missing_importers:
            ret['importers'] = self.plan_view.missing_importers
        if self.plan_view.missing_distributors:
            ret['distributors'] = self.plan_view.missing_distributors
        return ret


class _InternalMigrationPlan:
    def __init__(self, migration_plan):
        self._migration_plan = migration_plan

        self._plugin_plans = []
        for plugin_data in self._migration_plan['plugins']:
            self.plugin_plans.append(PluginMigrationPlan(plugin_data))

        self.repositories_missing_importers = []
        self.missing_repositories = []
        self.repositories_missing_distributors = []

        # Make sure we've initialized the MongoDB connection first
        connection.initialize()
        self._check_missing()

    @property
    def all_repositories_importers_to_migrate(self):
        # flat list of all importers to migrate
        return itertools.chain.from_iterable(
            [plugin.repositories_importers_to_migrate for plugin in self.plugin_plans]
        )

    @property
    def all_repositories_repositories_to_migrate(self):
        # flat list of all repositories to migrate
        return itertools.chain.from_iterable(
            [plugin.repositories_to_migrate for plugin in self.plugin_plans]
        )

    @property
    def all_repositories_distributors_to_migrate(self):
        # flat list of all distributors to migrate
        return itertools.chain.from_iterable(
            [plugin.repositories_distributors_to_migrate for plugin in self.plugin_plans]
        )

    def _check_missing(self):
        importers = Importer.objects(
            repo_id__in=self.all_repositories_importers_to_migrate).only('repo_id')
        present = set(importer.repo_id for importer in importers)
        expected = set(self.all_repositories_importers_to_migrate)

        self.repositories_missing_importers = list(expected - present)

        repositories = Repository.objects(
            repo_id__in=self.all_repositories_to_migrate).only('repo_id')
        present = set(repository.repo_id for repository in repositories)
        expected = set(self.all_repositories_to_migrate)

        self.missing_repositories = list(expected - present)

        distributors = Distributor.objects(
            distributor_id__in=self.all_repositories_distributors_to_migrate).only('distributor_id')
        present = set(distributor.distributor_id for distributor in distributors)
        expected = set(self.all_repositories_distributors_to_migrate)

        self.repositories_missing_distributors = list(expected - present)


class PluginMigrationPlan:
    """
    The migration plan for a specific plugin.
    """

    def __init__(self, plugin_migration_plan):
        """
        Init

        Args:
            plugin_migration_plan: Dictionary for the migration plan of a specific plugin.
        """
        self.repositories_importers_to_migrate = []
        self.repositories_to_migrate = []
        self.repositories_distributors_to_migrate = []

        self.repositories_to_create = {}
        self.type = None
        self.empty = True

        self._parse_plugin_plan(plugin_migration_plan)

    def _parse_plugin_plan(self, repository_data):
        self.type = repository_data['type']
        repositories = repository_data.get('repositories')

        if repositories:
            self.empty = False
            for repository in repositories:
                name = repository['name']

                _find_importer_repo = repository['pulp2_importer_repository_id']
                self.repositories_importers_to_migrate.append(_find_importer_repo)

                repository_versions = []
                for repository_version in repository.get('repository_versions', []):
                    pulp2_repository_id = repository_version['pulp2_repository_id']
                    self.repositories_to_migrate.append(pulp2_repository_id)
                    repository_versions.append(pulp2_repository_id)

                    distributor_ids = repository_version.get('distributor_ids', [])
                    self.repositories_distributors_to_migrate.extend(distributor_ids)

                self.repositories_to_create[name] = {
                    "pulp2_importer_repository_id": _find_importer_repo,
                    "versions": repository_versions
                }
