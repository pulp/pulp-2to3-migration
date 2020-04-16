import mongoengine

from pulp_2to3_migration.pulp2.base import (
    ContentUnit,
    FileContentUnit,
)


class DebPackage(FileContentUnit):
    """
    A model for the Pulp 2 DebPackge (deb content type).

    It will become a pulp_deb Package type in Pulp 3.
    """
    TYPE_ID = 'deb'
    UNIT_KEY_DEB = ("name", "version", "architecture", "checksumtype", "checksum")

    meta = {
        'collection': 'units_deb',
        'indexes': list(UNIT_KEY_DEB),
    }

    unit_key_fields = UNIT_KEY_DEB

    # Fields included in the ids.UNIT_KEY_DEB list:
    # Note: The first three of these are control file fields.
    name = mongoengine.StringField(required=True)
    version = mongoengine.StringField(required=True)
    architecture = mongoengine.StringField(required=True)
    # Note: checksumtype and checksum should only be used for pulp internals.
    # Use md5sum, sha1, and sha256 for publishing and similar.
    # Currently, checksumtype should always be 'sha256'
    checksumtype = mongoengine.StringField(required=True)
    checksum = mongoengine.StringField(required=True)

    # Other required fields:
    filename = mongoengine.StringField(required=True)

    REQUIRED_FIELDS = list(UNIT_KEY_DEB).append('filename')

    # Named checksum fields:
    md5sum = mongoengine.StringField()
    sha1 = mongoengine.StringField()
    sha256 = mongoengine.StringField()

    # Other non control file fields:
    # Note: Relativepath does not appear to be meaningfully in use.
    size = mongoengine.IntField()
    relativepath = mongoengine.StringField()

    # Relational fields:
    # Note: These are intended for structured relationship information. Raw
    # relationship field strings as used in Debian control files and Packages
    # indicies are stored in the control_fields dict instead.
    breaks = mongoengine.DynamicField()
    conflicts = mongoengine.DynamicField()
    depends = mongoengine.DynamicField()
    enhances = mongoengine.DynamicField()
    pre_depends = mongoengine.DynamicField()
    provides = mongoengine.DynamicField()
    recommends = mongoengine.DynamicField()
    replaces = mongoengine.DynamicField()
    suggests = mongoengine.DynamicField()

    # List of relational fields:
    REL_FIELDS = ['breaks', 'conflicts', 'depends', 'enhances', 'pre_depends',
                  'provides', 'recommends', 'replaces', 'suggests']

    # The control file fields dict:
    # Note: This stores a dict of strings as used within the python-debian
    # library. This allows us to retain all control file information, even for
    # fields not explicitly supported by pulp_deb.
    control_fields = mongoengine.DynamicField()

    # Remaining control file fields:
    # Note: With the addition of the control_fields dict, these fields contain
    # redundant information.
    source = mongoengine.StringField()
    maintainer = mongoengine.StringField()
    installed_size = mongoengine.StringField()
    section = mongoengine.StringField()
    priority = mongoengine.StringField()
    multi_arch = mongoengine.StringField()
    homepage = mongoengine.StringField()
    description = mongoengine.StringField()
    original_maintainer = mongoengine.StringField()

    # Fields retained for backwards compatibility:
    _ns = mongoengine.StringField(required=True, default=meta['collection'])
    _content_type_id = mongoengine.StringField(required=True, default=TYPE_ID)

    # A dict translating all control file field names from this class into their
    # python-debian (deb822) equivalent.
    # Note: Fields not found in control files are handled separately.
    TO_DEB822_MAP = dict(
        name="Package",
        version="Version",
        architecture="Architecture",
        breaks="Breaks",
        conflicts="Conflicts",
        depends="Depends",
        enhances="Enhances",
        pre_depends="Pre-Depends",
        provides="Provides",
        recommends="Recommends",
        replaces="Replaces",
        suggests="Suggests",
        source="Source",
        maintainer="Maintainer",
        installed_size="Installed-Size",
        section="Section",
        priority="Priority",
        multi_arch="Multi-Arch",
        homepage="Homepage",
        description="Description",
        original_maintainer="Original-Maintainer",
    )


class DebComponent(ContentUnit):
    """
    This unittype represents a deb release/distribution component.
    """
    TYPE_ID = 'deb_component'
    UNIT_KEY_DEB_COMPONENT = ('name', 'distribution', 'repoid')
    meta = {
        'collection': "units_deb_component",
        'indexes': list(UNIT_KEY_DEB_COMPONENT),
    }
    unit_key_fields = UNIT_KEY_DEB_COMPONENT

    name = mongoengine.StringField(required=True)
    distribution = mongoengine.StringField(required=True)
    release = mongoengine.StringField(required=True)
    repoid = mongoengine.StringField(required=True)
    packages = mongoengine.ListField()

    # For backward compatibility
    _ns = mongoengine.StringField(required=True, default=meta['collection'])
    _content_type_id = mongoengine.StringField(required=True, default=TYPE_ID)

    @property
    def plain_component(self):
        """
        Returns the plain component without any directory prefixes.
        """
        return self.name.strip('/').split('/')[-1]

    @property
    def prefixed_component(self):
        """
        Returns the component with additional directory prefixes for complex distributions.
        """
        prefix = '/'.join(self.distribution.split('/')[1:]).strip('/')
        return (prefix + '/' + self.plain_component).strip('/')


class DebRelease(ContentUnit):
    """
    This unittype represents a deb release (also referred to as a "distribution").
    """
    TYPE_ID = 'deb_release'
    UNIT_KEY_DEB_RELEASE = ('distribution', 'repoid')
    meta = dict(collection="units_deb_release", indexes=list(UNIT_KEY_DEB_RELEASE))
    unit_key_fields = UNIT_KEY_DEB_RELEASE

    repoid = mongoengine.StringField(required=True)
    distribution = mongoengine.StringField(required=True)
    codename = mongoengine.StringField(required=True)
    suite = mongoengine.StringField()

    # For backward compatibility
    _ns = mongoengine.StringField(required=True, default=meta['collection'])
    _content_type_id = mongoengine.StringField(required=True, default=TYPE_ID)
