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

        Doesn't return migration plans for plugins that don't have a migrator.
        """
        return [plugin for plugin in self.plan_view._plugin_plans if plugin.migrator]

    def get_plugins(self):
        """
        Return a list of pulp2 plugin names to migrate.
        """
        return [plugin.type for plugin in self.get_plugin_plans()]

    def get_missing_resources(self):
        """
        Return a dict of any resources listed in the plan but missing from Pulp 2.

        Repositories and Importers are enumerated by repo_id, Distributors by distributor_id.
        """
        ret = {}
        if self.plan_view.missing_repositories:
            ret['repositories'] = self.plan_view.missing_repositories
        if self.plan_view.repositories_missing_importers:
            ret['repositories_missing_importers'] = \
                self.plan_view.repositories_missing_importers
        if self.plan_view.repositories_missing_distributors:
            ret['repositories_missing_distributors'] = \
                self.plan_view.repositories_missing_distributors
        return ret


class _InternalMigrationPlan:
    def __init__(self, migration_plan):
        self._migration_plan = migration_plan
        self._plugin_plans = []

        for plugin_data in self._migration_plan['plugins']:
            self._plugin_plans.append(PluginMigrationPlan(plugin_data))

        self.repositories_missing_importers = []
        self.missing_repositories = []
        self.repositories_missing_distributors = []

        # Make sure we've initialized the MongoDB connection first
        connection.initialize()
        self._check_missing()

    @property
    def all_repositories_importers_to_migrate(self):
        # flat list of all importers to migrate
        return list(itertools.chain.from_iterable(
            [plugin.repositories_importers_to_migrate for plugin in self._plugin_plans]
        ))

    @property
    def all_repositories_to_migrate(self):
        # flat list of all repositories to migrate
        return list(itertools.chain.from_iterable(
            [plugin.repositories_to_migrate for plugin in self._plugin_plans]
        ))

    @property
    def all_repositories_distributors_to_migrate(self):
        # flat list of all distributors to migrate
        return list(itertools.chain.from_iterable(
            [plugin.repositories_distributors_to_migrate for plugin in self._plugin_plans]
        ))

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
        self.migrator = None
        self.empty = True

        self._parse_plugin_plan(plugin_migration_plan)

    def get_repositories(self):
        """
        Return a list of pulp2 repositories to migrate or empty list if all should be migrated.
        """
        return self.repositories_to_migrate

    def get_importers_repos(self):
        """
        Pulp2 repositories to migrate importers for or empty list if all should be migrated.
        """
        return self.repositories_importers_to_migrate

    def get_distributors_repos(self):
        """
        Pulp2 repositories to migrate distributors for or empty list if all should be migrated.
        """
        return self.repositories_distributors_to_migrate

    def get_repo_creation_setup(self):
        """
        Returns a structure that defines the Pulp 3 repositories to be created.

        e.g.

        {
            # name of the Pulp 3 repository to create
            'foo': {
                # id of the Pulp 2 repository whose importer should be the origin of the
                # created Pulp 3 remote
                'pulp2_importer_repository_id': "foo"
                # list of Pulp 2 repository IDs to use as the sources for created repo versions
                'repository_versions': [
                    # Repository Version 1 use contents of repo "idA" and distributions from the
                    # distributors in repos "pulp2_distributor_repository_id1" and
                    # "pulp2_distributor_repository_id2"
                    {
                        "pulp2_repository_id": "idA",
                        "pulp2_distributor_repository_ids":  [
                            "pulp2_distributor_repository_id1", "pulp2_distributor_repository_id2"
                        ]
                    },
                    {
                        "pulp2_repository_id": "idB",
                        "pulp2_distributor_repository_ids":  ["pulp2_distributor_repository_id3"]
                    },
                ]
            }
        }
        """
        return self.repositories_to_create

    def _parse_plugin_plan(self, repository_data):
        # Circular import avoidance
        from pulp_2to3_migration.app.plugin import PLUGIN_MIGRATORS

        self.type = repository_data['type']
        self.migrator = PLUGIN_MIGRATORS.get(self.type)

        repositories = repository_data.get('repositories')
        if repositories:
            self.empty = False
            for repository in repositories:
                name = repository['name']

                _find_importer_repo = repository.get('pulp2_importer_repository_id')
                if _find_importer_repo:
                    self.repositories_importers_to_migrate.append(_find_importer_repo)

                repository_versions = []
                for repository_version in repository.get('repository_versions', []):
                    pulp2_repository_id = repository_version['pulp2_repository_id']
                    self.repositories_to_migrate.append(pulp2_repository_id)

                    distributor_repo_ids = repository_version.get(
                        'pulp2_distributor_repository_ids', []
                    )
                    self.repositories_distributors_to_migrate.extend(distributor_repo_ids)

                    repository_versions.append(
                        {'repo_id': pulp2_repository_id, 'dist_repo_ids': distributor_repo_ids}
                    )

                self.repositories_to_create[name] = {
                    "pulp2_importer_repository_id": _find_importer_repo,
                    "repository_versions": repository_versions
                }
