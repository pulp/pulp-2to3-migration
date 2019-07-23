from django.db import models

from pulpcore.plugin.models import Model


class MigrationPlan(Model):
    """
    Migration Plans that have been created and maybe even run.

    Fields:
        plan (models.TextField): The migration plan in the JSON format
    """
    plan = models.TextField()


class Pulp2Content(Model):
    """
    General info about Pulp 2 content.

    Pulp3 plugin models should create a Foreign key to this model.

    Fields:
        pulp2_id (models.UUIDField): Content ID in Pulp 2
        pulp2_content_type_id (models.CharField): Content type in Pulp 2
        pulp2_last_updated (models.PositiveIntegerField): Content creation or update time in Pulp 2
        pulp2_storage_path (models.TextField): Content storage path on Pulp 2 system
        downloaded (models.BooleanField): Flag to identify if content is on a filesystem or not
    """
    pulp2_id = models.UUIDField()
    pulp2_content_type_id = models.CharField(max_length=255)
    pulp2_last_updated = models.PositiveIntegerField()
    pulp2_storage_path = models.TextField()
    downloaded = models.BooleanField(default=True)
