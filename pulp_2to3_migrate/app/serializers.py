from gettext import gettext as _

from rest_framework import serializers

from pulpcore.plugin.serializers import (
    ModelSerializer,
    IdentityField
)

from .models import MigrationPlan

class MigrationPlanSerializer(ModelSerializer):
    _href = IdentityField(
        view_name='migration-plans-detail'
    )

    plan = serializers.CharField(
        help_text= _('Migration Plan in JSON format'),
        required=True,
    )

    class Meta:
        fields = ModelSerializer.Meta.fields + ('plan', )
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
