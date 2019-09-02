from django.contrib.postgres.fields import JSONField

from pulpcore.plugin.models import Model


class MigrationPlan(Model):
    """
    Migration Plans that have been created and maybe even run.

    Fields:
        plan (models.JSONField): The migration plan in the JSON format
    """
    plan = JSONField()

    def get_repositories(self):
        """
        Return a list of pulp2 repositories to migrate or empty list if all should be migrated.
        """
        # TODO: get pulp2 repositories from the self.plan
        return []

    def get_importers(self):
        """
        Return a list of pulp2 importers to migrate or empty list if all should be migrated.
        """
        # TODO: get pulp2 importers from the self.plan
        return []

    def get_distributors(self):
        """
        Return a list of pulp2 distributors to migrate or empty list if all should be migrated.
        """
        # TODO: get pulp2 distributors from the self.plan
        return []
