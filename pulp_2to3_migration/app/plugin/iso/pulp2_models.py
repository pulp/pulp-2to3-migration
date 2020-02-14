import logging

from mongoengine import (
    IntField,
    StringField,
)

from pulp_2to3_migration.pulp2.base import FileContentUnit

_logger = logging.getLogger(__name__)


class ISO(FileContentUnit):
    """
    A model for Pulp 2 ISO content type.

    It will become a File content type in Pulp 3 world.
    """
    name = StringField(required=True)
    checksum = StringField(required=True)
    size = IntField(required=True)

    _ns = StringField(default='units_iso')
    _content_type_id = StringField(required=True, default='iso')

    unit_key_fields = ('name', 'checksum', 'size')
    unit_display_name = 'ISO'
    unit_description = 'ISO'

    TYPE_ID = 'iso'

    meta = {
        'collection': 'units_iso',
    }
