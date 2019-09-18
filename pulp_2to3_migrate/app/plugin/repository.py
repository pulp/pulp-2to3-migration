class Pulp2to3Importer:
    """
    Pulp 2to3 importer migration interface.

    Plugins should subclass it and define `migrate_to_pulp3` method.
    """
    class Meta:
        abstract = True

    @classmethod
    async def migrate_to_pulp3(cls, pulp2importer):
        """
        Migrate pre-migrated Pulp 2 importer.

        Args:
            pulp2importer(Pulp2Importer): Pre-migrated pulp2 importer to migrate

        Return:
            remote(Remote): Corresponding plugin Remote in Pulp3
            created(bool): True if Remote has just been created; False if Remote is an existing one

        """
        raise NotImplementedError()
