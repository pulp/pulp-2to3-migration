from mongoengine import (
    BooleanField,
    DateTimeField,
    DictField,
    Document,
    IntField,
    StringField,
)


class ContentUnit(Document):
    """
    The base class for all Pulp 2 content units.

    All classes inheriting from this class must define a _content_type_id and unit_key_fields.

    _content_type_id must be of type mongoengine.StringField and have a default value of the string
    name of the content type.

    unit_key_fields must be a tuple of strings, each of which is a valid field name of the subcalss.
    """
    id = StringField(primary_key=True)
    pulp_user_metadata = DictField()
    _last_updated = IntField(required=True)
    _storage_path = StringField()

    meta = {
        'abstract': True,
    }


class FileContentUnit(ContentUnit):
    """
    A Pulp 2 content unit representing content that is of type *file*.
    """
    downloaded = BooleanField()

    meta = {
        'abstract': True,
    }


class Repository(Document):
    """
    Defines schema for a pulp 2 repository in the `repos` collection.
    """
    repo_id = StringField(required=True, regex=r'^[.\-_A-Za-z0-9]+$')
    display_name = StringField()  # not used in the migration plugin
    description = StringField()
    notes = DictField()  # not used in the migration plugin
    scratchpad = DictField(default={})  # not used in the migration plugin
    content_unit_counts = DictField(default={})  # not used in the migration plugin
    last_unit_added = DateTimeField()
    last_unit_removed = DateTimeField()

    # For backward compatibility
    _ns = StringField(default='repos')

    meta = {'collection': 'repos',
            'allow_inheritance': False}


class RepositoryContentUnit(Document):
    """
    Represents the link between a pulp2 repository and the units associated with it.
    Defines the schema for the documents in repo_content_units collection.
    """
    repo_id = StringField(required=True)
    unit_id = StringField(required=True)
    unit_type_id = StringField(required=True)
    created = StringField(required=True)  # not used in the migration plugin
    updated = StringField(required=True)  # not used in the migration plugin

    # For backward compatibility
    _ns = StringField(default='repo_content_units')

    meta = {'collection': 'repo_content_units',
            'allow_inheritance': False}


class Importer(Document):
    """
    Defines schema for a pulp 2 importer in the `repo_importers` collection.
    """
    repo_id = StringField(required=True)
    importer_type_id = StringField(required=True)
    config = DictField()
    scratchpad = DictField(default=None)  # not used in the migration plugin
    last_sync = StringField()  # not used in the migration plugin
    last_updated = DateTimeField()
    last_override_config = DictField()  # not used in the migration plugin

    # For backward compatibility
    _ns = StringField(default='repo_importers')

    meta = {'collection': 'repo_importers',
            'allow_inheritance': False}


class Distributor(Document):
    """
    Defines schema for a pulp 2 distributor in the 'repo_distributors' collection.
    """
    repo_id = StringField(required=True)
    distributor_id = StringField(required=True, regex=r'^[\-_A-Za-z0-9]+$')
    distributor_type_id = StringField(required=True)
    config = DictField()
    auto_publish = BooleanField(default=False)
    last_publish = DateTimeField()  # not used in the migration plugin
    last_updated = DateTimeField()
    last_override_config = DictField()  # not used in the migration plugin
    scratchpad = DictField()  # not used in the migration plugin

    _ns = StringField(default='repo_distributors')

    meta = {'collection': 'repo_distributors',
            'allow_inheritance': False}


class LazyCatalogEntry(Document):
    """
    A Pulp 2 catalog of content that can be downloaded from a specific URL.
    """
    path = StringField(required=True)
    importer_id = StringField(required=True)
    unit_id = StringField(required=True)
    unit_type_id = StringField(required=True)
    url = StringField(required=True)
    checksum = StringField()  # not used in the migration plugin
    checksum_algorithm = StringField()  # not used in the migration plugin
    revision = IntField(default=1)
    data = DictField()  # not used in the migration plugin

    # For backward compatibility
    _ns = StringField(default='lazy_content_catalog')

    meta = {
        'collection': 'lazy_content_catalog',
        'allow_inheritance': False,
    }
