from pulpcore.plugin import PulpPluginAppConfig


class Pulp2To3MigrationPluginAppConfig(PulpPluginAppConfig):
    """Entry point for the pulp_2to3_migration plugin."""

    name = 'pulp_2to3_migration.app'
    label = 'pulp_2to3_migration'
    version = '0.7.0'
