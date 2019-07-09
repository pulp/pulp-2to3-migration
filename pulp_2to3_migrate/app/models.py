from django.db import models

from pulpcore.app.models import Task
from pulpcore.plugin.fields import JSONField
from pulpcore.plugin.models import Model


class MigrationPlan(Model):
    """
    Migration Plans that have been created and maybe even run.

    Fields:

        plan (models.TextField): The migration plan in the JSON format

    Relations:

        tasks (models.ManyToMany): The tasks associated with this MigrationPlan
    """
    plan = JSONField()
    tasks = models.ManyToManyField(Task, related_name='executed_migration_plan',
                                   through='TaskMigrationPlan')


class TaskMigrationPlan(Model):
    """
    Association between a MigrationPlan and the tasks which executed it.

    In order to have a one-to-many relationship, a task field is a one-to-one field.

    Relations:

        migration_plan (models.ForeignKey): The associated migration plan.
        task (models.ForeignKey): The associated task.
        """
    migration_plan = models.ForeignKey(MigrationPlan, on_delete=models.CASCADE)
    task = models.OneToOneField(Task, on_delete=models.CASCADE, default=Task.current)
