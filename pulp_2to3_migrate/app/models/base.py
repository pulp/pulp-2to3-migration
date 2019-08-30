from django.db import models
from django.contrib.postgres.fields import JSONField

from pulpcore.plugin.models import Model


class MigrationPlan(Model):
    """
    Migration Plans that have been created and maybe even run.

    Fields:
        plan (models.JSONField): The migration plan in the JSON format
    """

    plan = JSONField()
