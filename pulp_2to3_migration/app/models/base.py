from collections import defaultdict
import itertools

from django.contrib.postgres.fields import JSONField

from pulpcore.plugin.models import BaseModel

from pulp_2to3_migration.pulp2 import connection
from pulp_2to3_migration.pulp2.base import (
    Distributor,
    Importer,
    Repository,
    RepositoryContentUnit,
)


def get_repo_types(plan):
    """
    Create mappings for pulp 2 repository types.

    Identify type by inspecting content of a repo.
    One mapping is repo_id -> repo_type, the other is repo_type -> list of repo_ids.

    It's used later during pre-migration and identification of removed repos from pulp 2

    Args:
        plan(MigrationPlan): A Migration Plan

    Returns:
        repo_id_to_type(dict): mapping from a pulp 2 repo_id to a plugin/repo type
        type_to_repo_ids(dict): mapping from a plugin/repo type to the list of repo_ids

    """
    repo_id_to_type = {}
    type_to_repo_ids = defaultdict(set)

    # mapping content type -> plugin/repo type, e.g. 'docker_blob' -> 'docker'
    content_type_to_plugin = {}

    for plugin in plan.get_plugin_plans():
        for content_type in plugin.migrator.pulp2_content_models:
            content_type_to_plugin[content_type] = plugin.migrator.pulp2_plugin

        repos = set(plugin.get_repositories())
        repos |= set(plugin.get_importers_repos())
        repos |= set(plugin.get_distributors_repos())

        for repo in repos:
            repo_id_to_type[repo] = plugin.type
        type_to_repo_ids[plugin.type].update(repos)

    # TODO: optimizations.
    # It looks at each content at the moment. Potential optimizations:
    #  - This is a big query, paginate?
    #  - Filter by repos from the plan
    #  - Query any but one record for a repo
    for rec in RepositoryContentUnit.objects().\
            only('repo_id', 'unit_type_id').as_pymongo().no_cache():
        repo_id = rec['repo_id']
        unit_type_id = rec['unit_type_id']

        # a type for a repo is already known or this content/repo type is not supported
        if repo_id in repo_id_to_type or unit_type_id not in content_type_to_plugin:
            continue
        plugin_name = content_type_to_plugin[unit_type_id]
        repo_id_to_type[repo_id] = plugin_name
        type_to_repo_ids[plugin_name].add(repo_id)

    return repo_id_to_type, type_to_repo_ids


class MigrationPlan(BaseModel):
    """
    Migration Plans that have been created and maybe even run.

    Fields:
        plan (models.JSONField): The migration plan in the JSON format
    """
    plan = JSONField()
    _real_plan = None

    # A mapping from a pulp 2 repo_id to pulp 2 repo type
    repo_id_to_type = None
    # A mapping from a pulp 2 repo type to a list of pulp 2 repo_ids
    type_to_repo_ids = None

    @property
    def plan_view(self):
        """
        Cached and validated migration plan.

        Lazy because we don't want to do parsing on empty objects.
        """
        if not self._real_plan:
            self._real_plan = _InternalMigrationPlan(self)
            (self.repo_id_to_type, self.type_to_repo_ids) = get_repo_types(self)

            # can't use the .get_plugin_plans() method from here due to recursion problem
            for plugin_plan in self._real_plan._plugin_plans:
                if plugin_plan.empty:
                    # plan was "empty", we need to automatically backfill the information from what
                    # exists in pulp 2. This is really tricky and a little messy, because it needs
                    # to happen after the migration plan has been parsed.
                    repository_ids = self.type_to_repo_ids[plugin_plan.type]
                    repositories = Repository.objects().filter(
                        repo_id__in=repository_ids
                    ).only("repo_id")

                    for repository in repositories.as_pymongo().no_cache():
                        repo_id = repository['repo_id']
                        plugin_plan.repositories_to_create[repo_id] = {
                            "pulp2_importer_repository_id": repo_id,
                            "repository_versions": [
                                {
                                    "repo_id": repo_id,
                                    "dist_repo_ids": [repo_id],
                                }
                            ]
                        }

                        plugin_plan.repositories_importers_to_migrate.append(repo_id)
                        plugin_plan.repositories_to_migrate.append(repo_id)
                        plugin_plan.repositories_distributors_to_migrate.append(repo_id)

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
        self._plugin_plans = []

        for plugin_data in migration_plan.plan['plugins']:
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
            repo_id__in=self.all_repositories_distributors_to_migrate).only('repo_id')
        present = set(distributor.repo_id for distributor in distributors)
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
            plugin_migration_plan (dict): The migration plan for a specific plugin.
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
