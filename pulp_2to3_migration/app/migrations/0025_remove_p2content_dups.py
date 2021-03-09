# Generated by Django 2.2.19 on 2021-03-09 01:47

from django.db import migrations, models


def fix_dups(apps, schema_editor):
    pulp2content = apps.get_model("pulp_2to3_migration", "Pulp2Content")
    # find sets of p2-id/p2-type/-2-repo/p2-sub dups
    p2content = pulp2content.objects.values('pulp2_id', 'pulp2_content_type_id', 'pulp2_repo_id', 'pulp2_subid').order_by('-pulp2_id')
    p2content = p2content.annotate(count_id=models.Count("pulp2_id")).filter(count_id__gt=1)

    # for each set of dups...
    for dup in p2content:
        # ...find the pulp-ids of entries in that set (ordering by pulp2-last-update such that
        # newest(largest-timestamp) is first entry).
        unique_keys = {x: dup[x] for x in ['pulp2_id', 'pulp2_content_type_id', 'pulp2_repo_id', 'pulp2_subid']}
        to_delete = pulp2content.objects.filter(**unique_keys).order_by('-pulp2_last_updated')
        # exclude the first/newest one...
        to_delete = to_delete.exclude(pk=to_delete[0].pk)
        # ...and delete the rest
        to_delete.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pulp_2to3_migration', '0024_reposetup'),
    ]

    operations = [
        migrations.RunPython(fix_dups),
    ]
