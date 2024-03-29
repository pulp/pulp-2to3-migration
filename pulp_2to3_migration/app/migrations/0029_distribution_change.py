# Generated by Django 2.2.24 on 2021-06-07 15:14

import logging
from django.db import migrations, models
import django.db.models.deletion

_logger = logging.getLogger(__name__)


def unset_distribution_field(apps, schema_editor):
    Pulp2Distributor = apps.get_model("pulp_2to3_migration", "pulp2distributor")
    nrows = Pulp2Distributor.objects.update(pulp3_distribution=None, is_migrated=False)
    _logger.debug("Updated {} Pulp2Distributor rows.".format(nrows))


class Migration(migrations.Migration):

    dependencies = [
        ("pulp_2to3_migration", "0028_create_missing_indices"),
    ]

    operations = [
        migrations.RunPython(
            code=unset_distribution_field,
        ),
        migrations.AlterField(
            model_name="pulp2distributor",
            name="pulp3_distribution",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="core.Distribution",
            ),
        ),
    ]
