# Generated by Django 2.2.16 on 2020-11-11 20:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pulp_2to3_migration", "0015_add_created_updated"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="pulp2content",
            index=models.Index(
                fields=["pulp2_content_type_id"], name="pulp_2to3_m_pulp2_c_7621eb_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="pulp2distributor",
            index=models.Index(
                fields=["pulp2_type_id"], name="pulp_2to3_m_pulp2_t_f161fa_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="pulp2importer",
            index=models.Index(
                fields=["pulp2_type_id"], name="pulp_2to3_m_pulp2_t_e87f6f_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="pulp2repocontent",
            index=models.Index(
                fields=["pulp2_content_type_id"], name="pulp_2to3_m_pulp2_c_6007dc_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="pulp2repository",
            index=models.Index(
                fields=["pulp2_repo_type"], name="pulp_2to3_m_pulp2_r_536467_idx"
            ),
        ),
    ]
