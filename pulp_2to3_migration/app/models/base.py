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
        Window to view the validated migration plan data through.
        """
        if not self._real_plan:
            self._real_plan = _InternalMigrationPlan(self.plan)

        return self._real_plan

    def get_plugins(self):
        """
        Return a list of pulp2 plugins to migrate.
        """
        return self.plan_view.plugins_to_migrate

    def get_repositories(self):
        """
        Return a list of pulp2 repositories to migrate or empty list if all should be migrated.
        """
        return self.plan_view.repositories_to_migrate

    def get_pulp3_repository_setup(self):
        """
        Return a dict of pulp3 repositories to create and information about e.g. versions.
        """
        return self.plan_view.repositories_to_create

    def get_importers(self):
        """
        Pulp2 repositories to migrate importers for or empty list if all should be migrated.
        """
        return self.plan_view.repositories_importers_to_migrate

    def get_distributors(self):
        """
        Pulp2 repositories to migrate distributors for or empty list if all should be migrated.
        """
        return self.plan_view.repositories_distributors_to_migrate

    def get_missing_resources(self):
        """
        Return a dict of any resources listed in the plan but missing from Pulp 2.
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
        self.migration_plan = migration_plan

        self.plugins_to_migrate = []
        self.repositories_importers_to_migrate = []
        self.repositories_distributors_to_migrate = []
        # pre-migration *just* needs these repos and nothing else
        self.repositories_to_migrate = []

        # a nested data structure with a format roughly matching the JSON schema.
        # dictionary where the key is the name of the pulp3 repo and the value is a dict
        # of other information like repo_versions, importer to use, etc.
        self.repositories_to_create = {}

        self.missing_importers = []     # _repositories_ with missing importers
        self.missing_repositories = []
        self.missing_distributors = []  # _repositories_ with missing distributors

        # Make sure we've initialized the MongoDB connection first
        connection.initialize()
        self._populate()

    def _populate(self):
        for plugin_data in self.migration_plan['plugins']:
            self.plugins_to_migrate.append(plugin_data['type'])
            if plugin_data.get('repositories'):
                self._parse_repository_data(plugin_data.get('repositories'))

        importers = Importer.objects(
            repo_id__in=self.repositories_importers_to_migrate).only('repo_id')
        present = set(importer.repo_id for importer in importers)
        expected = set(self.repository_importers_to_migrate)

        self.missing_importers = list(expected - present)

        repositories = Repository.objects(
            repo_id__in=self.repositories_to_migrate).only('repo_id')
        present = set(repository.repo_id for repository in repositories)
        expected = set(self.repositories_to_migrate)

        self.missing_repositories = list(expected - present)

        distributors = Distributor.objects(
            repo_id__in=self.repositories_distributors_to_migrate).only('repo_id')
        present = set(distributor.repo_id for distributor in distributors)
        expected = set(self.repository_distributors_to_migrate)

        self.missing_distributors = list(expected - present)

    def _parse_repository_data(self, repository_data):
        for repository in repository_data:
            name = repository['name']

            _find_importer_repo = repository['pulp2_importer_repository_id']
            self.repository_importers_to_migrate.append(_find_importer_repo)

            repository_versions = self._parse_repository_version_data(
                repository.get('repository_versions', [])
            )

            repository_data = {
                "pulp2_importer_repository_id": _find_importer_repo,
                "versions": repository_versions
            }

            self.repositories_to_create[name] = repository_data

    def _parse_repository_version_data(self, repository_version_data):
        repository_versions = []

        for repository_version in repository_version_data:
            pulp2_repository_id = repository_version['pulp2_repository_id']
            self.repositories_to_migrate.append(pulp2_repository_id)
            repository_versions.append(pulp2_repository_id)

            distributor_repository_ids = repository_version.get(
                'pulp2_distributor_repository_ids', []
            )
            self.repository_distributors_to_migrate.extend(distributor_repository_ids)

        return repository_versions
