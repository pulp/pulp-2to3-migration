from django.contrib.postgres.fields import JSONField
from django.db import models

from pulp_2to3_migration.app.models import Pulp2to3Content

from .pulp2_models import (
    Errata,
    RPM,
)


class Pulp2Rpm(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store Pulp 2 RPM content details for Pulp 3 content creation.
    """

    name = models.TextField()
    epoch = models.TextField()
    version = models.TextField()
    release = models.TextField()
    arch = models.TextField()
    checksum = models.TextField()
    checksumtype = models.TextField()

    repodata = JSONField(dict)
    is_modular = models.BooleanField(default=False)
    size = models.PositiveIntegerField()
    filename = models.TextField()

    pulp2_type = 'rpm'

    class Meta:
        unique_together = (
            'name', 'epoch', 'version', 'release', 'arch', 'checksumtype', 'checksum',
            'pulp2content')
        default_related_name = 'rpm_detail_model'

    @property
    def expected_digests(self):
        """Return expected digests."""
        return {self.checksumtype: self.checksum}

    @property
    def expected_size(self):
        """Return expected size."""
        return self.size

    @property
    def relative_path_for_content_artifact(self):
        """Return relative path."""
        return self.filename

    @classmethod
    async def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 RPM content with all the fields needed to create a Pulp 3 Package.

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.

        """
        pulp2_id_obj_map = {pulp2content.pulp2_id: pulp2content for pulp2content in content_batch}
        pulp2_ids = pulp2_id_obj_map.keys()
        pulp2_rpm_content_batch = RPM.objects.filter(id__in=pulp2_ids)
        pulp2rpm_to_save = [
            cls(name=rpm.name,
                epoch=rpm.epoch,
                version=rpm.version,
                release=rpm.release,
                arch=rpm.arch,
                checksum=rpm.checksum,
                checksumtype=rpm.checksumtype,
                repodata=rpm.repodata,
                is_modular=rpm.is_modular,
                size=rpm.size,
                filename=rpm.filename,
                pulp2content=pulp2_id_obj_map[rpm.id])
            for rpm in pulp2_rpm_content_batch]
        cls.objects.bulk_create(pulp2rpm_to_save, ignore_conflicts=True)


class Pulp2Erratum(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store Pulp2 Errata content details.
    """

    # Required fields
    errata_id = models.TextField(unique=True)
    updated = models.TextField()

    issued = models.TextField()
    status = models.TextField()
    description = models.TextField()
    pushcount = models.TextField()
    references = JSONField()
    reboot_suggested = models.BooleanField()
    relogin_suggested = models.BooleanField()
    restart_suggested = models.BooleanField()
    errata_from = models.TextField()
    severity = models.TextField()
    rights = models.TextField()
    version = models.TextField()
    release = models.TextField()
    errata_type = models.TextField()
    pkglist = JSONField()
    title = models.TextField()
    solution = models.TextField()
    summary = models.TextField()

    pulp2_type = 'erratum'

    class Meta:
        default_related_name = 'erratum_detail_model'

    @classmethod
    async def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 Erratum content with all the fields needed to create a Pulp 3 Package.

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.

        """
        pulp2_id_obj_map = {pulp2content.pulp2_id: pulp2content for pulp2content in content_batch}
        pulp2_ids = pulp2_id_obj_map.keys()
        pulp2_erratum_content_batch = Errata.objects.filter(id__in=pulp2_ids)
        pulp2erratum_to_save = [
            cls(errata_id=erratum.errata_id,
                updated=erratum.updated,
                issued=erratum.issued,
                status=erratum.status,
                description=erratum.description,
                pushcount=erratum.pushcount,
                references=erratum.references,
                reboot_suggested=erratum.reboot_suggested,
                relogin_suggested=erratum.relogin_suggested,
                restart_suggested=erratum.restart_suggested,
                errata_from=erratum.errata_from,
                severity=erratum.severity,
                rights=erratum.rights,
                version=erratum.version,
                release=erratum.release,
                errata_type=erratum.type,
                pkglist=erratum.pkglist,
                title=erratum.title,
                solution=erratum.solution,
                summary=erratum.summary,
                pulp2content=pulp2_id_obj_map[erratum.id])
            for erratum in pulp2_erratum_content_batch]
        cls.objects.bulk_create(pulp2erratum_to_save, ignore_conflicts=True)
