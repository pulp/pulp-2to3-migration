import logging

from mongoengine import (
    BooleanField,
    DictField,
    Document,
    FloatField,
    IntField,
    ListField,
    StringField,
)

from pulp_2to3_migration.pulp2.base import (
    ContentUnit,
    FileContentUnit,
)

_logger = logging.getLogger(__name__)


class NonMetadataPackage(FileContentUnit):
    """
    An abstract Pulp 2 model to be subclassed by packages which are not metadata.
    """

    version = StringField(required=True)
    release = StringField(required=True)
    checksum = StringField(required=True)
    checksumtype = StringField(required=True)
    checksums = DictField()
    signing_key = StringField()  # not used in the migration plugin

    version_sort_index = StringField()  # not used in the migration plugin
    release_sort_index = StringField()  # not used in the migration plugin

    meta = {
        'abstract': True,
    }


class RpmBase(NonMetadataPackage):
    """
    An abstract model designed to be sub-classed by both RPM and SRPM.

    RPM amd SRPM package types are similar. Most fields map to metadata fields in the RPM package
    format.
    """

    # Unit Key Fields
    name = StringField(required=True)
    epoch = StringField(required=True)
    version = StringField(required=True)
    release = StringField(required=True)
    arch = StringField(required=True)

    # Other Fields
    build_time = IntField()  # not used in the migration plugin
    buildhost = StringField()  # not used in the migration plugin
    vendor = StringField()  # not used in the migration plugin
    size = IntField()
    base_url = StringField()  # not used in the migration plugin
    filename = StringField()
    relative_url_path = StringField()  # not used in the migration plugin
    relativepath = StringField()  # not used in the migration plugin
    group = StringField()  # not used in the migration plugin

    provides = ListField()  # not used in the migration plugin
    files = DictField()  # not used in the migration plugin
    repodata = DictField(default={})
    description = StringField()  # not used in the migration plugin
    header_range = DictField()  # not used in the migration plugin
    sourcerpm = StringField()  # not used in the migration plugin
    license = StringField()  # not used in the migration plugin
    changelog = ListField()  # not used in the migration plugin
    url = StringField()  # not used in the migration plugin
    summary = StringField()  # not used in the migration plugin
    time = IntField()  # not used in the migration plugin
    requires = ListField()  # not used in the migration plugin
    recommends = ListField()  # not used in the migration plugin

    unit_key_fields = ('name', 'epoch', 'version', 'release', 'arch', 'checksumtype', 'checksum')

    meta = {
        'indexes': [
            "name", "epoch", "version", "release", "arch", "filename", "checksum", "checksumtype",
            "version_sort_index", ("version_sort_index", "release_sort_index")
        ],
        'abstract': True,
    }


class RPM(RpmBase):
    """
    A model for Pulp 2 RPM content type.

    It will become a Package content type in Pulp 3 world.
    """
    TYPE_ID = 'rpm'

    # For backward compatibility
    _ns = StringField(default='units_rpm')
    _content_type_id = StringField(required=True, default=TYPE_ID)

    unit_display_name = 'RPM'
    unit_description = 'RPM'
    unit_referenced_types = ['erratum']

    is_modular = BooleanField(default=False)

    meta = {
        'collection': 'units_rpm',
        'allow_inheritance': False,
    }


class SRPM(RpmBase):
    """
    A model for Pulp 2 SRPM content type.

    It will become a Package content type in Pulp 3 world.
    """
    TYPE_ID = 'srpm'

    # For backward compatibility
    _ns = StringField(default='units_srpm')
    _content_type_id = StringField(required=True, default='srpm')

    unit_display_name = 'SRPM'
    unit_description = 'SRPM'

    meta = {
        'collection': 'units_srpm',
        'allow_inheritance': False}


class Errata(ContentUnit):
    """
    A model for Pulp 2 Erratum content type.

    It will become an Advisory content type in Pulp 3 world.
    """
    TYPE_ID = 'erratum'

    errata_id = StringField(required=True)
    status = StringField()
    updated = StringField(required=True, default='')
    description = StringField()
    issued = StringField()
    pushcount = StringField()
    references = ListField()
    reboot_suggested = BooleanField()
    relogin_suggested = BooleanField()
    restart_suggested = BooleanField()
    errata_from = StringField(db_field='from')
    severity = StringField()
    rights = StringField()
    version = StringField()
    release = StringField()
    type = StringField()
    pkglist = ListField()
    title = StringField()
    solution = StringField()
    summary = StringField()

    # For backward compatibility
    _ns = StringField(default='units_erratum')
    _content_type_id = StringField(required=True, default='erratum')

    unit_key_fields = ('errata_id',)
    unit_display_name = 'Erratum'
    unit_description = 'Erratum advisory information'
    unit_referenced_types = ['rpm']

    meta = {
        'indexes': [
            "version", "release", "type", "status", "updated", "issued", "severity", "references"
        ],
        'collection': 'units_erratum',
        'allow_inheritance': False,
    }


class ErratumPkglist(Document):
    """
    A model for erratum pkglists. It's needed to retrieve pkglists for errata migration.

    For each erratum there can be multiple pkglists but they refer to different repo_id's.
    It is not guaranteed that for every repo containing an erratum there is a pkglist with
    corresponding repo_id. If erratum was copied from one repo to the other (and not imported
    via sync or upload), no new pkglist is created i pulp 2.
    During migration all the pkglists related to an erratum are used and filtered out accordingly.
    """
    errata_id = StringField(required=True)
    repo_id = StringField(required=True)
    collections = ListField()

    _ns = StringField(default='erratum_pkglists')

    model_key_fields = ('errata_id', 'repo_id')
    meta = {'collection': 'erratum_pkglists',
            'allow_inheritance': False,
            'indexes': ['errata_id',
                        {'fields': model_key_fields, 'unique': True}]}


class YumMetadataFile(FileContentUnit):
    """
    A model for Pulp 2 YumMetadataFile content type.

    It will become a RepoMetadataFile content type in Pulp 3 world.
    """

    data_type = StringField(required=True)
    repo_id = StringField(required=True)

    checksum = StringField()
    checksum_type = StringField()

    # For backward compatibility
    _ns = StringField(default='units_yum_repo_metadata_file')
    _content_type_id = StringField(required=True, default='yum_repo_metadata_file')

    unit_key_fields = ('data_type', 'repo_id')
    unit_display_name = 'YUM Repository Metadata File'
    unit_description = 'YUM Repository Metadata File'

    TYPE_ID = 'yum_repo_metadata_file'

    meta = {
        'indexes': ['data_type'],
        'collection': 'units_yum_repo_metadata_file',
        'allow_inheritance': False}


class Modulemd(FileContentUnit):
    """
    A model for Pulp 2 Modulemd content type.
    """
    TYPE_ID = 'modulemd'

    # Unit key fields NSVCA
    name = StringField(required=True)
    stream = StringField(required=True)
    version = IntField(required=True)
    context = StringField(required=True)
    arch = StringField(required=True)

    summary = StringField()
    description = StringField()
    profiles = DictField()
    artifacts = ListField()
    checksum = StringField()
    dependencies = ListField()

    # For backward compatibility
    _ns = StringField(default='units_modulemd')
    _content_type_id = StringField(required=True, default=TYPE_ID)

    unit_key_fields = ('name', 'stream', 'version', 'context', 'arch', )
    unit_display_name = 'Modulemd'
    unit_description = 'Modulemd'

    meta = {'collection': 'units_modulemd',
            'indexes': ['artifacts'],
            'allow_inheritance': False}


class ModulemdDefaults(FileContentUnit):
    """
    A model for Pulp 2 Modulemd content type.
    """
    TYPE_ID = 'modulemd_defaults'

    # Unit key fields
    name = StringField(required=True)
    repo_id = StringField(required=True)

    stream = StringField()
    profiles = StringField()

    checksum = StringField()

    # For backward compatibility
    _ns = StringField(default='units_modulemd_defaults')
    _content_type_id = StringField(required=True, default=TYPE_ID)

    unit_key_fields = ('name', 'repo_id',)
    unit_display_name = 'ModulemdDefaults'
    unit_description = 'ModulemdDefaults'

    meta = {'collection': 'units_modulemd_defaults',
            'indexes': ['repo_id'],
            'allow_inheritance': False}


class Distribution(FileContentUnit):
    """
    Model for a Pulp 2 RPM distribution tree (also sometimes referenced as an installable tree).
    A distribution tree is described by a file in root of an RPM repository named either
    "treeinfo" or ".treeinfo".
    """
    TYPE_ID = 'distribution'

    distribution_id = StringField(required=True)
    family = StringField(required=True)
    variant = StringField(default='')
    version = StringField(required=True)
    arch = StringField(required=True)

    files = ListField()
    timestamp = FloatField()
    packagedir = StringField()

    # Pretty sure the version_sort_index is never used for Distribution units
    version_sort_index = StringField()

    # For backward compatibility
    _ns = StringField(default='units_distribution')
    _content_type_id = StringField(required=True, default='distribution')

    unit_key_fields = ('distribution_id', 'family', 'variant', 'version', 'arch')
    unit_display_name = 'Distribution'
    unit_description = 'Kickstart trees and all accompanying files'

    meta = {'collection': 'units_distribution',
            'indexes': ['distribution_id', 'family', 'variant', 'version', 'arch'],
            'allow_inheritance': False}


class PackageGroup(ContentUnit):
    """
    A model for Pulp 2 PackageGroup content type.
    """
    TYPE_ID = 'package_group'

    package_group_id = StringField(required=True)
    repo_id = StringField(required=True)

    description = StringField()
    default_package_names = ListField()
    optional_package_names = ListField()
    mandatory_package_names = ListField()
    name = StringField()
    default = BooleanField(default=False)
    display_order = IntField()
    user_visible = BooleanField(default=False)
    translated_name = DictField()
    translated_description = DictField()
    langonly = StringField()
    conditional_package_names = ListField()

    # For backward compatibility
    _ns = StringField(default='units_package_group')
    _content_type_id = StringField(required=True, default=TYPE_ID)

    unit_key_fields = ('package_group_id', 'repo_id')
    unit_display_name = 'Package Group'
    unit_description = 'Yum Package group information'

    meta = {
        'indexes': [
            'package_group_id', 'repo_id', 'name', 'mandatory_package_names',
            'conditional_package_names', 'optional_package_names', 'default_package_names'
        ],
        'collection': 'units_package_group',
        'allow_inheritance': False}


class PackageCategory(ContentUnit):
    """
    A model for Pulp 2 PackageCategory content type.
    """
    TYPE_ID = 'package_category'

    package_category_id = StringField(required=True)
    repo_id = StringField(required=True)

    description = StringField()
    packagegroupids = ListField()
    translated_description = DictField()
    translated_name = DictField()
    display_order = IntField()
    name = StringField()

    # For backward compatibility
    _ns = StringField(default='units_package_category')
    _content_type_id = StringField(required=True, default=TYPE_ID)

    unit_key_fields = ('package_category_id', 'repo_id')
    unit_display_name = 'Package Category'
    unit_description = 'Yum Package category information'

    meta = {
        'indexes': [
            'package_category_id', 'repo_id', 'name', 'packagegroupids'
        ],
        'collection': 'units_package_category',
        'allow_inheritance': False}


class PackageEnvironment(ContentUnit):
    """
    A model for Pulp 2 PackageEnvironment content type.
    """
    TYPE_ID = 'package_environment'

    package_environment_id = StringField(required=True)
    repo_id = StringField(required=True)

    group_ids = ListField()
    description = StringField()
    translated_name = DictField()
    translated_description = DictField()
    options = ListField()
    display_order = IntField()
    name = StringField()

    # For backward compatibility
    _ns = StringField(default='units_package_environment')
    _content_type_id = StringField(required=True, default=TYPE_ID)

    unit_key_fields = ('package_environment_id', 'repo_id')
    unit_display_name = 'Package Environment'
    unit_description = 'Yum Package environment information'

    meta = {
        'indexes': ['package_environment_id', 'repo_id', 'name', 'group_ids'],
        'collection': 'units_package_environment',
        'allow_inheritance': False}


class PackageLangpacks(ContentUnit):
    """
    A model for Pulp 2 PackageLangpacks content type.
    """
    TYPE_ID = 'package_langpacks'

    repo_id = StringField(required=True)
    matches = ListField()

    # For backward compatibility
    _ns = StringField(default='units_package_langpacks')
    _content_type_id = StringField(required=True, default=TYPE_ID)

    unit_key_fields = ('repo_id',)

    meta = {
        'collection': 'units_package_langpacks',
        'allow_inheritance': False}
