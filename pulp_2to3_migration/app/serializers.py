import json

from gettext import gettext as _
from jsonschema import Draft7Validator
from pymongo.errors import OperationFailure
from rest_framework import serializers

from pulp_2to3_migration.app.plugin import PLUGIN_MIGRATORS
from pulp_2to3_migration.pulp2 import connection

from pulpcore.app.settings import INSTALLED_PULP_PLUGINS
from pulpcore.plugin.serializers import (
    ModelSerializer,
    DetailRelatedField,
    IdentityField
)

from .json_schema import SCHEMA
from .models import MigrationPlan, Pulp2Content


class MigrationPlanSerializer(ModelSerializer):
    """Serializer for migration plan model."""
    _href = IdentityField(
        view_name='migration-plans-detail'
    )

    plan = serializers.JSONField(
        help_text=_('Migration Plan in JSON format'),
        required=True,
    )

    class Meta:
        fields = ModelSerializer.Meta.fields + ('plan', )
        model = MigrationPlan

    def validate(self, data):
        """
        Validate that the Serializer contains valid data.

        Validates JSON structure of migration_plan.
        Checks pulp2 and pulp3 plugins are installed.
        """
        schema = json.loads(SCHEMA)
        validator = Draft7Validator(schema)
        loaded_plan = json.loads(data['plan'])
        err = []
        for error in sorted(validator.iter_errors(loaded_plan), key=str):
            err.append(error.message)
        if err:
            raise serializers.ValidationError(
                _("Provided Migration Plan format is invalid:'{}'".format(err))
            )
        plugins_to_migrate = set()
        for plugin_type in loaded_plan['plugins']:
            plugins_to_migrate.add(plugin_type['type'])
        if len(loaded_plan['plugins']) != len(plugins_to_migrate):
            raise serializers.ValidationError(
                _("Provided Migration Plan contains same plugin type specified more that once.")
            )
        # MongoDB connection initialization
        connection.initialize()
        db = connection.get_database()
        for plugin in plugins_to_migrate:
            plugin_migrator = PLUGIN_MIGRATORS.get(plugin)
            if not plugin_migrator:
                raise serializers.ValidationError(
                    _("Migraiton of {} plugin is not supported.".format(plugin))
                )
            if plugin_migrator.pulp3_plugin not in INSTALLED_PULP_PLUGINS:
                raise serializers.ValidationError(
                    _("Plugin {} is not installed in pulp3.".format(plugin))
                )
            try:
                db.command("collstats", plugin_migrator.pulp2_collection)
            except OperationFailure:
                raise serializers.ValidationError(
                    _("Plugin {} is not installed in pulp2.".format(plugin))
                )
        data['plan'] = loaded_plan
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


class Pulp2ContentSerializer(ModelSerializer):
    """
    A serializer for the Pulp2Content model
    """
    _href = IdentityField(
        view_name='migration-plans-detail'
    )
    pulp2_id = serializers.CharField(max_length=255)
    pulp2_content_type_id = serializers.CharField(max_length=255)
    pulp2_last_updated = serializers.IntegerField()
    pulp2_storage_path = serializers.CharField()
    downloaded = serializers.BooleanField(default=False)
    pulp3_content = DetailRelatedField(
        required=False, allow_null=True, queryset=Pulp2Content.objects.all()
    )

    class Meta:
        fields = ModelSerializer.Meta.fields + ('pulp2_id', 'pulp2_content_type_id',
                                                'pulp2_last_updated', 'pulp2_storage_path',
                                                'downloaded', 'pulp3_content')
        model = Pulp2Content
