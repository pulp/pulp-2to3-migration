# Generated by Django 2.2.11 on 2020-03-20 12:19

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("pulp_2to3_migration", "0004_modularity_metafile_erratum_rpm"),
    ]

    operations = [
        migrations.CreateModel(
            name="Pulp2Distribution",
            fields=[
                (
                    "pulp_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("pulp_created", models.DateTimeField(auto_now_add=True)),
                ("pulp_last_updated", models.DateTimeField(auto_now=True, null=True)),
                ("distribution_id", models.TextField()),
                ("family", models.TextField()),
                ("variant", models.TextField()),
                ("version", models.TextField()),
                ("arch", models.TextField()),
                (
                    "pulp2content",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="distribution_detail_model",
                        to="pulp_2to3_migration.Pulp2Content",
                    ),
                ),
            ],
            options={
                "default_related_name": "distribution_detail_model",
                "unique_together": {
                    (
                        "distribution_id",
                        "family",
                        "variant",
                        "version",
                        "arch",
                        "pulp2content",
                    )
                },
            },
        ),
    ]
