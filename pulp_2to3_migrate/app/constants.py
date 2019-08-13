# for tasking system to ensure only one migration is run at a time
PULP_2TO3_MIGRATION_RESOURCE = 'pulp_2to3_migration'

# Pulp2 plugins and their content types which can be migrated
# 'pulp2_plugin': 'pulp_2to3_migrate pulp2 model class name'
SUPPORTED_PULP2_PLUGINS = {
    'iso': ['ISO'],
    # 'rpm': [
    #     'Distribution',
    #     'Drpm',
    #     'Erratum',
    #     'Modulemd',
    #     'ModulemdDefaults',
    #     'PackageCategory',
    #     'PackageEnvironment',
    #     'PackageGroup',
    #     'PackageLangpacks',
    #     'Rpm',
    #     'Srpm',
    #     'YumRepoMetadataFile'],
    # 'docker': [
    #     'Blob',
    #     'Image',
    #     'Manifest',
    #     'ManifestList',
    #     'Tag'],
}

# 'pulp2_content_type_id': 'pulp_2to3_migrate pulp3 model class name '
PULP_2TO3_CONTENT_MODEL_MAP = {
    'iso': 'Pulp2ISO',
}

# For manfatory parameters which won't be used by migration tool, e.g. in Declarative Version
NOT_USED = 'Not Used'
