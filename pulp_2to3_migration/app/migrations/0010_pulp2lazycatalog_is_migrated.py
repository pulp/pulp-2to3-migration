# Generated by Django 2.2.12 on 2020-04-29 16:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pulp_2to3_migration", "0009_pulp2erratum_allow_null"),
    ]

    operations = [
        migrations.AddField(
            model_name="pulp2lazycatalog",
            name="is_migrated",
            field=models.BooleanField(default=False),
        ),
    ]
