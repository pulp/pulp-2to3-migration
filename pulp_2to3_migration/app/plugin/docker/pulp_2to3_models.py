from django.db import models
from django.contrib.postgres.fields import ArrayField

from pulp_2to3_migration.app.models import Pulp2to3Content

from pulp_container.constants import MEDIA_TYPE
from pulp_container.app.models import Blob, Manifest, Tag

from . import pulp2_models


class Pulp2Blob(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store Pulp 2 Blob content details
    for Pulp 3 content creation.
    """
    digest = models.CharField(max_length=255)
    media_type = models.CharField(max_length=80)

    pulp2_type = 'docker_blob'
    checksum_type = 'sha256'

    class Meta:
        unique_together = ('digest', 'pulp2content')
        default_related_name = 'docker_blob_detail_model'

    @property
    def expected_digests(self):
        """Return expected digests."""
        return {self.checksum_type: self.digest.split(':')[1]}

    @property
    def expected_size(self):
        """Return expected size."""
        return

    @property
    def relative_path_for_content_artifact(self):
        """Return relative path."""
        return self.digest

    @classmethod
    def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 Blob content with all the fields needed to create a Pulp 3 Blob

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.

        """
        pulp2_id_obj_map = {pulp2content.pulp2_id: pulp2content for pulp2content in content_batch}
        pulp2_ids = pulp2_id_obj_map.keys()
        pulp2_blob_content_batch = pulp2_models.Blob.objects.filter(id__in=pulp2_ids)
        pulp2blob_to_save = [Pulp2Blob(digest=blob.digest,
                                       media_type=MEDIA_TYPE.REGULAR_BLOB,
                                       pulp2content=pulp2_id_obj_map[blob.id])
                             for blob in pulp2_blob_content_batch]
        cls.objects.bulk_create(pulp2blob_to_save, ignore_conflicts=True)

    def create_pulp3_content(self):
        """
        Create a Pulp 3 Blob unit for saving it later in a bulk operation.
        """
        return (Blob(digest=self.digest, media_type=self.media_type), None)


class Pulp2Manifest(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store pulp 2 Manifest content details
    for Pulp 3 content creation.
    """
    digest = models.CharField(max_length=255)
    schema_version = models.IntegerField()
    media_type = models.CharField(max_length=80)
    blobs = ArrayField(models.CharField(max_length=255))
    config_blob = models.CharField(max_length=255, null=True)

    pulp2_type = 'docker_manifest'
    checksum_type = 'sha256'

    class Meta:
        unique_together = ('digest', 'pulp2content')
        default_related_name = 'docker_manifest_detail_model'

    @property
    def expected_digests(self):
        """Return expected digests."""
        return {}

    @property
    def expected_size(self):
        """Return expected size."""
        return

    @property
    def relative_path_for_content_artifact(self):
        """Return relative path."""
        return self.digest

    @classmethod
    def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 Manifest content with all the fields needed to create a Pulp 3 Manifest

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.

        """
        def _get_media_type(schema_version):
            """
            Return media_type of the manifest.
            """
            return MEDIA_TYPE.MANIFEST_V2 if schema_version == 2 else MEDIA_TYPE.MANIFEST_V1

        def _get_blobs(layers):
            """
            Return list of regular blobs that manifest contains.
            """
            blobs = []
            for layer in layers:
                if layer.layer_type != MEDIA_TYPE.FOREIGN_BLOB:
                    blobs.append(layer.blob_sum)
            return blobs

        pulp2_id_obj_map = {pulp2content.pulp2_id: pulp2content for pulp2content in content_batch}
        pulp2_ids = pulp2_id_obj_map.keys()
        pulp2_m_content_batch = pulp2_models.Manifest.objects.filter(id__in=pulp2_ids)
        pulp2m_to_save = []
        for m in pulp2_m_content_batch:
            pulp2m_to_save.append(
                Pulp2Manifest(digest=m.digest,
                              media_type=_get_media_type(m.schema_version),
                              schema_version=m.schema_version,
                              config_blob=m.config_layer,
                              blobs=_get_blobs(m.fs_layers),
                              pulp2content=pulp2_id_obj_map[m.id])
            )
        cls.objects.bulk_create(pulp2m_to_save, ignore_conflicts=True)

    def create_pulp3_content(self):
        """
        Create a Pulp 3 Manifest unit for saving it later in a bulk operation.
        """
        future_relations = {'blob_rel': self.blobs, 'config_blob_rel': self.config_blob}
        return (Manifest(digest=self.digest,
                         media_type=self.media_type,
                         schema_version=self.schema_version), future_relations)


class Pulp2ManifestList(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store pulp 2 ManifestList content details
    for Pulp 3 content creation.
    """
    digest = models.CharField(max_length=255)
    media_type = models.CharField(max_length=80)
    schema_version = models.IntegerField()
    media_type = models.CharField(max_length=80)
    listed_manifests = ArrayField(models.CharField(max_length=255))

    pulp2_type = 'docker_manifest_list'
    checksum_type = 'sha256'

    class Meta:
        unique_together = ('digest', 'pulp2content')
        default_related_name = 'docker_manifest_list_detail_model'

    @property
    def expected_digests(self):
        """Return expected digests."""
        return {self.checksum_type: self.digest.split(':')[1]}

    @property
    def expected_size(self):
        """Return expected size."""
        return

    @property
    def relative_path_for_content_artifact(self):
        """Return relative path."""
        return self.digest

    @classmethod
    def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 ManifestList content with all the fields needed to create
        a Pulp 3 Manifest

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.

        """
        pulp2_id_obj_map = {pulp2content.pulp2_id: pulp2content for pulp2content in content_batch}
        pulp2_ids = pulp2_id_obj_map.keys()
        pulp2_m_content_batch = pulp2_models.ManifestList.objects.filter(id__in=pulp2_ids)
        pulp2m_to_save = [Pulp2ManifestList(digest=m.digest,
                                            media_type=MEDIA_TYPE.MANIFEST_LIST,
                                            schema_version=m.schema_version,
                                            listed_manifests=[man.digest for man in m.manifests],
                                            pulp2content=pulp2_id_obj_map[m.id])
                          for m in pulp2_m_content_batch]
        cls.objects.bulk_create(pulp2m_to_save, ignore_conflicts=True)

    def create_pulp3_content(self):
        """
        Create a Pulp 3 Manifest unit for saving it later in a bulk operation.
        """
        future_relations = {'man_rel': self.listed_manifests}
        return (Manifest(digest=self.digest,
                         media_type=self.media_type,
                         schema_version=self.schema_version), future_relations)


class Pulp2Tag(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store pulp 2 Tag content details
    for Pulp 3 content creation.
    """
    name = models.TextField()
    tagged_manifest = models.CharField(max_length=255)
    repo_id = models.TextField()

    pulp2_type = 'docker_tag'
    checksum_type = 'sha256'

    class Meta:
        unique_together = ('name', 'tagged_manifest', 'repo_id', 'pulp2content')
        default_related_name = 'docker_tag_detail_model'

    @property
    def relative_path_for_content_artifact(self):
        """Return relative path."""
        return self.name

    @classmethod
    def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 Tag content with all the fields needed to create a Pulp 3 Tag

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.

        """
        pulp2_id_obj_map = {pulp2content.pulp2_id: pulp2content for pulp2content in content_batch}
        pulp2_ids = pulp2_id_obj_map.keys()
        pulp2_tag_content_batch = pulp2_models.Tag.objects.filter(id__in=pulp2_ids)
        pulp2tag_to_save = [Pulp2Tag(name=tag.name,
                                     tagged_manifest=tag.manifest_digest,
                                     repo_id=tag.repo_id,
                                     pulp2content=pulp2_id_obj_map[tag.id])
                            for tag in pulp2_tag_content_batch]
        cls.objects.bulk_create(pulp2tag_to_save, ignore_conflicts=True)

    def create_pulp3_content(self):
        """
        Create a Pulp 3 Tag unit for saving it later in a bulk operation.
        """
        future_relations = {'tag_rel': self.tagged_manifest}
        return (Tag(name=self.name), future_relations)
