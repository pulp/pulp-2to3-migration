class Pulp2to3PluginMigrator:
    """
    Class to serve as a plugin interface for migration to Pulp 3.

    Attributes:
        type(str): migrator type which corresponds to a Pulp 2 plugin name
        content_models(tuple): Pulp2to3Content models this migrator is responsible for
    """
    type = 'pulp2 plugin name'
    content_models = ()

    @classmethod
    async def migrate_to_pulp3(cls):
        """
        Migrate all pre-migrated plugin content to Pulp 3.

        Create a DeclatativeContentMigration pipeline here and instantiate it with your first stage.
        Here the default implementation of the first stage is used:
        >>> first_stage = ContentMigrationFirstStage(cls)
        >>> dm = DeclarativeContentMigration(first_stage=first_stage)
        >>> await dm.create()
        """
        raise NotImplementedError()
