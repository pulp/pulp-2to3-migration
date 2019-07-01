from django.db import models

from pulpcore.plugin.models import Model


class MigrationPlan(Model):
    plan = models.TextField()
