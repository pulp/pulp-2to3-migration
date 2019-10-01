# for tasking system to ensure only one migration is run at a time
PULP_2TO3_MIGRATION_RESOURCE = 'pulp_2to3_migration'

PULP_2TO3_POLICIES = {
    'immediate': 'immediate',
    'on_demand': 'on_demand',
    'background': 'on_demand',
}

NOT_USED = 'Not Used'
