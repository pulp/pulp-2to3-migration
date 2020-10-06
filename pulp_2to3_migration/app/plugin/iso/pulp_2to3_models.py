from django.db import models

from pulp_2to3_migration.app.constants import DEFAULT_BATCH_SIZE
from pulp_2to3_migration.app.models import Pulp2to3Content

from pulp_file.app.models import FileContent

from .pulp2_models import ISO


class Pulp2ISO(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store pulp 2 ISO content details for Pulp 3 content creation.
    """
    name = models.TextField()
    checksum = models.CharField(max_length=64)
    size = models.BigIntegerField()

    pulp2_type = 'iso'
    checksum_type = 'sha256'

    class Meta:
        unique_together = ('name', 'checksum', 'size', 'pulp2content')
        default_related_name = 'iso_detail_model'

    @property
    def expected_digests(self):
        """Return expected digests."""
        return {self.checksum_type: self.checksum}

    @property
    def expected_size(self):
        """Return expected size."""
        return self.size

    @property
    def relative_path_for_content_artifact(self):
        """Return relative path."""
        return self.name

    @classmethod
    def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 ISO content with all the fields needed to create a Pulp 3 FileContent

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.

        """
        # TODO: all pulp2content objects from the batch are in memory. Concerns?
        pulp2_id_obj_map = {pulp2content.pulp2_id: pulp2content for pulp2content in content_batch}
        pulp2_ids = pulp2_id_obj_map.keys()
        pulp2_iso_content_batch = ISO.objects.filter(id__in=pulp2_ids)
        pulp2iso_to_save = [Pulp2ISO(name=iso.name,
                                     checksum=iso.checksum,
                                     size=iso.size,
                                     pulp2content=pulp2_id_obj_map[iso.id])
                            for iso in pulp2_iso_content_batch]
        cls.objects.bulk_create(pulp2iso_to_save, ignore_conflicts=True,
                                batch_size=DEFAULT_BATCH_SIZE)

    def create_pulp3_content(self):
        """
        Create a Pulp 3 FileContent unit for saving it later in a bulk operation.
        """
        return (FileContent(relative_path=self.name,
                            digest=self.checksum), None)
