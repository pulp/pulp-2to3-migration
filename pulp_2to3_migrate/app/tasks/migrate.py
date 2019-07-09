import time

from pulp_2to3_migrate.app.models import (
    MigrationPlan,
    TaskMigrationPlan
)


def migrate_from_pulp2(migration_plan_pk, dry_run=False):
    """
    Main task to migrate from Pulp 2 to Pulp 3.

    Schedule other tasks based on the specified Migration Plan.

    Args:
        migration_plan_pk (str): The migration plan PK.
        dry_run (bool): If True, nothing is migrated, only validation happens.
    """
    migration_plan = MigrationPlan.objects.get(pk=migration_plan_pk)
    associated_task = TaskMigrationPlan(migration_plan=migration_plan)
    associated_task.save()
    time.sleep(1)
