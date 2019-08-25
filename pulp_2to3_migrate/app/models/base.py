from django.db import models

from pulpcore.plugin.models import Model


class MigrationPlan(Model):
    """
    Migration Plans that have been created and maybe even run.

    Fields:
        plan (models.TextField): The migration plan in the JSON format
    """
    plan = models.TextField()
    # TODO: convert to JSONField
