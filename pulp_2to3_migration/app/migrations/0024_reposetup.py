# Generated by Django 2.2.17 on 2021-02-22 18:34

from django.db import migrations, models
import django_lifecycle.mixins
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("pulp_2to3_migration", "0023_remove_pulp2importer_repo_field"),
    ]

    operations = [
        migrations.CreateModel(
            name="RepoSetup",
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
                ("pulp2_repo_id", models.TextField()),
                ("pulp2_repo_type", models.CharField(max_length=25)),
                ("pulp2_resource_repo_id", models.TextField(blank=True)),
                (
                    "pulp2_resource_type",
                    models.SmallIntegerField(
                        choices=[(0, "importer"), (1, "distributor")]
                    ),
                ),
                (
                    "status",
                    models.SmallIntegerField(
                        choices=[(0, "old"), (1, "up to date"), (2, "new")]
                    ),
                ),
            ],
            bases=(django_lifecycle.mixins.LifecycleModelMixin, models.Model),
        ),
        migrations.AddIndex(
            model_name="reposetup",
            index=models.Index(
                fields=["pulp2_resource_type"], name="pulp_2to3_m_pulp2_r_d9a309_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="reposetup",
            index=models.Index(fields=["status"], name="pulp_2to3_m_status_47e94a_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="reposetup",
            unique_together={
                ("pulp2_repo_id", "pulp2_resource_repo_id", "pulp2_resource_type")
            },
        ),
    ]
