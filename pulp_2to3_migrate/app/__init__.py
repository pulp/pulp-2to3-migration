from pulpcore.plugin import PulpPluginAppConfig


class Pulp2To3MigratePluginAppConfig(PulpPluginAppConfig):
    """Entry point for the pulp_2to3_migrate plugin."""

    name = 'pulp_2to3_migrate.app'
    label = 'pulp_2to3_migrate'
