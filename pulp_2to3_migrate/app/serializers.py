from gettext import gettext as _

from rest_framework import serializers
from rest_framework.reverse import reverse

from pulpcore.plugin.serializers import (
    IdentityField,
    ModelSerializer,
)

from .models import MigrationPlan


class TasksFieldSerializer(IdentityField):
    """
    Serializer to return a list of hrefs for associated tasks.
    """
    def to_representation(self, data):
        ret = []
        for task in data.tasks.get_queryset():
            href = reverse(self.view_name, kwargs={'pk': task.pk})
            ret.append(href)
        return ret


class MigrationPlanSerializer(ModelSerializer):
    _href = IdentityField(
        view_name='migration-plans-detail'
    )

    plan = serializers.JSONField(
        help_text=_('Migration Plan in JSON format'),
        required=True,
    )

    tasks = TasksFieldSerializer(
        help_text=_('Tasks which used this Migration Plan'),
        read_only=True,
        view_name='tasks-detail'
    )

    class Meta:
        fields = ModelSerializer.Meta.fields + ('plan', 'tasks')
        model = MigrationPlan

    def validate(self, data):
        """
        Validate that the Serializer contains valid data.

        TODO:
        Validate JSON structure of migration_plan.
        Check validity of the JSON content:
         - migration for requested plugins is supported

        """
        return data


class MigrationPlanRunSerializer(serializers.Serializer):
    """
    A serializer for running a migration plan.
    """
    dry_run = serializers.BooleanField(
        help_text=_('If ``True``, performs validation of a Migration Plan only, no migration is '
                    'run. If ``False``, both validation and migration are run.'),
        required=False,
        default=False,
        write_only=True
    )
