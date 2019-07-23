# for tasking system to ensure only one migration is run at a time
PULP_2TO3_MIGRATION_RESOURCE = 'pulp_2to3_migration'

# Pulp2 plugins and their content types which can be migrated
# 'pulp2_plugin': 'pulp2 model class name'
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

# Mapping Pulp 2 content type to Pulp 3 plugin and content type
# 'pulp2 content type id' -> ('pulp3 plugin', 'pulp3 content type')
PULP_2TO3_TYPE_MAP = {
    'iso': ('file', 'file'),
    # 'erratum': ('rpm', 'advisory'),
    # 'rpm': ('rpm': 'package'),
}
