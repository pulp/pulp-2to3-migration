import logging

from mongoengine import (
    EmbeddedDocument,
    EmbeddedDocumentField,
    IntField,
    ListField,
    StringField,
)

from pulp_2to3_migration.pulp2.base import FileContentUnit, ContentUnit

_logger = logging.getLogger(__name__)


class Blob(FileContentUnit):
    """
    A model for Pulp 2 Blob content type.

    It will become a Blob content type in Pulp 3 world.
    """
    digest = StringField(required=True)

    _ns = StringField(default='units_docker_blob')
    _content_type_id = StringField(required=True, default='docker_blob')

    unit_key_fields = ('digest')
    unit_display_name = 'docker blob'
    unit_description = 'docker blob'

    TYPE_ID = 'docker_blob'

    meta = {
        'collection': 'units_docker_blob',
    }


class FSLayer(EmbeddedDocument):
    """
    This EmbeddedDocument is used in the Manifest.fs_layers field. It references a Blob Document.
    """
    # This will be the digest of a Blob document.
    blob_sum = StringField(required=True)
    size = IntField()
    layer_type = StringField()


class Manifest(FileContentUnit):
    """
    This model represents a Docker v2, Schema 1 Image Manifest and Schema 2 Image Manifest.
    """
    digest = StringField(required=True)
    schema_version = IntField(required=True)
    fs_layers = ListField(field=EmbeddedDocumentField(FSLayer), required=True)
    config_layer = StringField()

    # For backward compatibility
    _ns = StringField(default='units_docker_manfest')
    _content_type_id = StringField(required=True, default='docker_manifest')

    unit_key_fields = ('digest',)
    unit_display_name = 'docker manifest'
    unit_description = 'docker manifest'

    TYPE_ID = 'docker_manifest'

    meta = {
        'collection': 'units_docker_manifest',
    }


class EmbeddedManifest(EmbeddedDocument):
    """
    This EmbeddedDocument is used in the ManifestList.manifests field.
    It references a ManifestList.
    """
    digest = StringField(required=True)
    os = StringField()
    arch = StringField()


class ManifestList(FileContentUnit):
    """
    This model represents a Docker v2, Schema 2 Manifest list
    """
    digest = StringField(required=True)
    schema_version = IntField(required=True)
    manifests = ListField(EmbeddedDocumentField(EmbeddedManifest))
    amd64_digest = StringField()
    amd64_schema_version = IntField()

    # For backward compatibility
    _ns = StringField(default='units_docker_manifest_list')
    _content_type_id = StringField(required=True, default='docker_manifest_list')

    unit_key_fields = ('digest',)
    unit_display_name = 'docker manifest list'
    unit_description = 'docker manifest list'

    TYPE_ID = 'docker_manifest_list'

    meta = {
        'collection': 'units_docker_manifest_list',
    }


class Tag(ContentUnit):
    """
    This class is used to represent Docker v2 tags.
    """
    name = StringField(required=True)
    manifest_digest = StringField(required=True)
    repo_id = StringField(required=True)
    schema_version = IntField(required=True)
    manifest_type = StringField(required=True)

    _ns = StringField(default='units_docker_tag')
    _content_type_id = StringField(required=True, default='docker_tag')

    unit_key_fields = ('name', 'repo_id', 'schema_version', 'manifest_type')
    unit_display_name = 'docker tag'
    unit_description = 'docker tag'

    TYPE_ID = 'docker_tag'

    meta = {
        'collection': 'units_docker_tag',
    }
