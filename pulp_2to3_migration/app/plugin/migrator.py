class Pulp2to3PluginMigrator:
    """
    Class to serve as a plugin interface for migration to Pulp 3.

    The attributes described below are expected to be defined by plugin writers.

    Attributes:
        pulp2_plugin(str): Pulp 2 plugin name
        pulp2_content_models(dict): {'pulp2 content_type_id': 'content class to access MongoDB'}
        pulp2_collection(str): a pulp2 collection which existence signifies that a plugin
                               is installed in pulp2
        pulp3_plugin(str): Pulp 3 plugin name
        pulp3_repository(class): Pulp 3 Repository model
        content_models(dict): {'pulp2 content_type_id': 'detail content class to pre-migrate to'}
        importer_migrators(dict): {'importer_type_id': 'pulp_2to3 importer interface/migrator'}

    """
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
