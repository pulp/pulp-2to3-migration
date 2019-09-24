# temporary hack, to move gradually to one migrator
from pulp_2to3_migration.app.plugin.iso.pulp3.migrator import IsoMigrator

# for tasking system to ensure only one migration is run at a time
PULP_2TO3_MIGRATION_RESOURCE = 'pulp_2to3_migration'

# Pulp2 plugins and their content types which can be migrated
# 'pulp2_plugin': 'pulp_2to3_migration pulp2 model class name'
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

# 'pulp2_content_type_id': 'pulp_2to3_migration pulp3 model class name '
PULP_2TO3_CONTENT_MODEL_MAP = {
    'iso': 'Pulp2ISO',
}


PULP_2TO3_PLUGIN_MAP = {
    'iso': 'pulp_file',
    # 'docker' : 'pulp_container',
    # 'rpm' : 'pulp_rpm',
}

PULP2_COLLECTION_MAP = {
    'iso': 'units_iso',
    # 'docker': 'units_docker_manifest',
    # 'rpm': 'units_rpm',
}

PULP_2TO3_POLICIES = {
   'immediate': 'immediate',
   'on_demand': 'on_demand',
   'background': 'on_demand',
}

# 'pulp2 plugin': [('pulp2 importer_type_id', 'pulp_2to3 plugin importer migration model'), ... ]
PULP_2TO3_IMPORTER_TYPE_MODEL_MAP = {
    'iso': [('iso_importer', 'IsoImporter')]
}

# 'pulp2 plugin': [('pulp2 distributor_type_id', 'pulp_2to3 plugin distributor migration model'),
#                  ... ]
# PULP_2TO3_DISTRIBUTOR_TYPE_MODEL_MAP = {
#     'iso': [('iso_distributor', 'IsoDistributor'),]
# }

PLUGIN_MIGRATORS_MAP = {
    'iso': IsoMigrator
}
