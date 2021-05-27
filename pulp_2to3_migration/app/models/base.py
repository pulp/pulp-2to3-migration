import itertools
from collections import defaultdict

from django.contrib.postgres.fields import JSONField
from django.db import IntegrityError, models

from pulpcore.plugin.models import BaseModel

from pulp_2to3_migration.pulp2 import connection
from pulp_2to3_migration.pulp2.base import (
    Distributor,
    Importer,
    Repository,
    RepositoryContentUnit,
)

from .repository import Pulp2Repository


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
    is_simple_plan = False

    # mapping content type -> plugin/repo type, e.g. 'docker_blob' -> 'docker'
    content_type_to_plugin = {}

    for plugin in plan.get_plugin_plans():
        for content_type in plugin.migrator.pulp2_content_models:
            content_type_to_plugin[content_type] = plugin.migrator.pulp2_plugin

        # if any of the plugin plans is empty, we'd need to go through all repo content relations
        # to determine repo types correctly.
        if plugin.empty:
            is_simple_plan = True
            continue

        repos = set(plugin.get_repositories())
        repos |= set(plugin.get_importers_repos())
        repos |= set(plugin.get_distributors_repos())

        for repo in repos:
            repo_id_to_type[repo] = plugin.type
        type_to_repo_ids[plugin.type].update(repos)

    # Go through repo content relations only when at least one of the plans is not complex,
    # otherwise the type is determined by the plan in a much more efficient way.
    if is_simple_plan:
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
                        RepoSetup.set_importer(repo_id, plugin_plan.type, importer_repo_id=repo_id)
                        RepoSetup.set_distributors(
                            repo_id, plugin_plan.type, distributor_repo_ids=[repo_id]
                        )

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

                importer_repo_id = repository.get('pulp2_importer_repository_id')
                if importer_repo_id:
                    self.repositories_importers_to_migrate.append(importer_repo_id)

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

                    RepoSetup.set_importer(pulp2_repository_id, self.type, importer_repo_id)
                    RepoSetup.set_distributors(pulp2_repository_id, self.type, distributor_repo_ids)

                self.repositories_to_create[name] = {
                    "pulp2_importer_repository_id": importer_repo_id,
                    "repository_versions": repository_versions
                }


class RepoSetup(BaseModel):
    """
    A model to reflect changes between previous and current migration plans.

    Fields:
        pulp2_repo_id (models.TextField): pulp2_repo_id to migrate into a repo_version
        pulp2_repo_type (models.CharField): pulp2 repo type
        pulp2_resource_repo_id (models.TextField): pulp2_repo_id of the resource
            (importer/distributor) to migrate
        pulp2_resource_type (models.SmallIntegerField): pulp2 resource type - importer/distributor
        status (models.SmallIntegerField): status of the record

    """
    OLD = 0
    UP_TO_DATE = 1
    NEW = 2
    STATUS_CHOICES = (
        (OLD, 'old'),
        (UP_TO_DATE, 'up to date'),
        (NEW, 'new'),
    )

    IMPORTER = 0
    DISTRIBUTOR = 1
    RESOURCE_TYPE_CHOICES = (
        (IMPORTER, 'importer'),
        (DISTRIBUTOR, 'distributor')
    )

    pulp2_repo_id = models.TextField()
    pulp2_repo_type = models.CharField(max_length=25)
    pulp2_resource_repo_id = models.TextField(blank=True)
    pulp2_resource_type = models.SmallIntegerField(choices=RESOURCE_TYPE_CHOICES)
    status = models.SmallIntegerField(choices=STATUS_CHOICES)

    class Meta:
        unique_together = ('pulp2_repo_id', 'pulp2_resource_repo_id', 'pulp2_resource_type')
        indexes = [
            models.Index(fields=['pulp2_resource_type']),
            models.Index(fields=['status'])
        ]

    @classmethod
    def finalize(cls, plugins):
        """
        Finalize RepoSetup process.

        For that the following needs to be performed in specified order:
         - remove records that are marked as old ones for the plugins in the plan (they are
         leftovers from the old run)
         - set status for all records to `old`, as a sign of completion of the RepoSetup process.

        It is only safe to do after the premigration step is done.
        If premigration was interrupted, all records should stay as they are.

        Args:
            plugins(list): List of plugin names specified in the Migration Plan
        """
        cls.objects.filter(pulp2_repo_type__in=plugins, status=cls.OLD).delete()
        cls.objects.filter().update(status=cls.OLD)

    @classmethod
    def reset_plugin(cls, plugin_type):
        """
        Remove all records for a specified plugin.

        Args:
            plugin_type(str): pulp2 plugin name to reset
        """
        cls.objects.filter(pulp2_repo_type=plugin_type).delete()

    @classmethod
    def set_importer(cls, repo_id, repo_type, importer_repo_id):
        """
        Sets proper status for the `repo_id`, `importer_repo_id` pair:
         - `up to date` for the relations which stayed the same
         - `new` for absolutely new ones or if a repository had a different importer according to
           the previous plan

        If previous premigration failed, we should be careful not to override any in `new` state
        with `up to date` ones, to let the `new` ones be processed (potentially for the second
        time).

        Args:
            repo_id(str): pulp 2 repository id
            repo_type(str): pulp 2 repo type
            importer_repo_id(str): pulp 2 repository id of an importer
        """
        relation, created = cls.objects.get_or_create(
            pulp2_resource_type=cls.IMPORTER,
            pulp2_repo_type=repo_type,
            pulp2_repo_id=repo_id,
            pulp2_resource_repo_id=importer_repo_id or '',
            defaults={'status': cls.NEW}
        )

        is_unchanged_relation = not created and relation.status == cls.OLD
        if is_unchanged_relation:
            relation.status = cls.UP_TO_DATE
            relation.save()

    @classmethod
    def set_distributors(cls, repo_id, repo_type, distributor_repo_ids):
        """
        Sets proper status for the `repo_id`, `distributor_repo_id` pairs:
         - `up to date` for the relations which stayed the same
         - `new` for absolutely new ones or if a repository had different distributors according to
           the previous plan

        If previous premigration failed, we should be careful not to override any in `new` state
        with `up to date` ones, to let the `new` ones be processed (potentially for the second
        time).

        Args:
            repo_id(str): pulp 2 repository id
            repo_type(str): pulp 2 repo type
            distributor_repo_ids(list): pulp 2 repository ids of distributors
        """
        up_to_date_count = cls.objects.filter(
            pulp2_repo_id=repo_id,
            pulp2_resource_type=cls.DISTRIBUTOR,
            pulp2_resource_repo_id__in=distributor_repo_ids,
            status=cls.OLD
        ).update(status=cls.UP_TO_DATE)

        no_new_relations = up_to_date_count == len(distributor_repo_ids)
        if no_new_relations:
            return

        # create new relations
        for distributor_repo_id in distributor_repo_ids:
            try:
                cls.objects.create(
                    pulp2_resource_type=cls.DISTRIBUTOR,
                    pulp2_repo_type=repo_type,
                    pulp2_repo_id=repo_id,
                    pulp2_resource_repo_id=distributor_repo_id or '',
                    status=cls.NEW,
                )
            except IntegrityError:
                # ignore existing relations, they've been already updated as up to date ones
                pass

    @classmethod
    def mark_changed_relations(cls, plugins):
        """
        Set is_migrated to False for any relations which changed and no longer up to date.

        Args:
            plugins(list): List of plugin names specified in the Migration Plan
        """
        changed_relations_repo_ids = RepoSetup.objects.filter(pulp2_repo_type__in=plugins).exclude(
            status=cls.UP_TO_DATE
        ).only('pulp2_repo_id').values_list('pulp2_repo_id', flat=True)
        Pulp2Repository.objects.filter(
            pulp2_repo_id__in=changed_relations_repo_ids
        ).update(is_migrated=False)
