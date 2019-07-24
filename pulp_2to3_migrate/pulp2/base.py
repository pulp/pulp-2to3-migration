from mongoengine import (
    BooleanField,
    DictField,
    Document,
    IntField,
    StringField
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
