import json

from debian import deb822

from django.db import models as django_models

from pulp_deb.app import models as pulp3_models
from pulp_deb.app.serializers import Package822Serializer

from pulp_2to3_migration.app.constants import DEFAULT_BATCH_SIZE
from pulp_2to3_migration.app.models import Pulp2to3Content

from . import pulp2_models


class Pulp2DebPackage(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store pulp 2 DebPackage content details for Pulp 3
    content creation.
    """
    pulp2_type = 'deb'
    checksumtype = django_models.TextField()
    checksum = django_models.TextField()
    filename = django_models.TextField()
    size = django_models.BigIntegerField()
    extra_control_fields = django_models.TextField(null=True)
    # Known control fields:
    package = django_models.TextField()
    source = django_models.TextField(null=True)
    version = django_models.TextField()
    essential = django_models.TextField(null=True)
    installed_size = django_models.TextField(null=True)
    maintainer = django_models.TextField(null=True)
    original_maintainer = django_models.TextField(null=True)
    architecture = django_models.TextField()
    replaces = django_models.TextField(null=True)
    provides = django_models.TextField(null=True)
    depends = django_models.TextField(null=True)
    pre_depends = django_models.TextField(null=True)
    recommends = django_models.TextField(null=True)
    suggests = django_models.TextField(null=True)
    enhances = django_models.TextField(null=True)
    conflicts = django_models.TextField(null=True)
    breaks = django_models.TextField(null=True)
    description = django_models.TextField(null=True)
    multi_arch = django_models.TextField(null=True)
    homepage = django_models.TextField(null=True)
    built_using = django_models.TextField(null=True)
    description_md5 = django_models.TextField(null=True)
    build_essential = django_models.TextField(null=True)
    tag = django_models.TextField(null=True)
    section = django_models.TextField(null=True)
    priority = django_models.TextField(null=True)

    # Ordered list of control file fields explicitly known to pulp_deb:
    control_field_map = {
        'package': 'Package',
        'source': 'Source',
        'version': 'Version',
        'essential': 'Essential',
        'installed_size': 'Installed-Size',
        'maintainer': 'Maintainer',
        'original_maintainer': 'Original-Maintainer',
        'architecture': 'Architecture',
        'replaces': 'Replaces',
        'provides': 'Provides',
        'depends': 'Depends',
        'pre_depends': 'Pre-Depends',
        'recommends': 'Recommends',
        'suggests': 'Suggests',
        'enhances': 'Enhances',
        'conflicts': 'Conflicts',
        'breaks': 'Breaks',
        'description': 'Description',
        'multi_arch': 'Multi-Arch',
        'homepage': 'Homepage',
        'built_using': 'Built-Using',
        'description_md5': 'Description-md5',
        'build_essential': 'Build-Essential',
        'tag': 'Tag',
        'section': 'Section',
        'priority': 'Priority',
    }

    class Meta:
        default_related_name = 'deb_detail_model'
        unique_together = (
            'package',
            'version',
            'architecture',
            'checksumtype',
            'checksum',
            'pulp2content',
        )

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
    def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 content with all the fields needed to create a Pulp 3 Content.

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.
        """
        pulp2_unit_fields = set([
            'checksumtype',
            'checksum',
            'filename',
            'size',
            'control_fields',
        ])
        pulp2_id_obj_map = {pulp2content.pulp2_id: pulp2content for pulp2content in content_batch}
        pulp2_ids = pulp2_id_obj_map.keys()
        pulp2_content_batch = pulp2_models.DebPackage.objects.filter(
            id__in=pulp2_ids,
        ).as_pymongo().only(*pulp2_unit_fields)

        pulp2deb_to_save = []
        for deb in pulp2_content_batch:
            pre_migrate_fields = {k: deb['control_fields'][v]
                                  for k, v in cls.control_field_map.items()
                                  if v in deb['control_fields'].keys()}
            keys = deb['control_fields'].keys() - cls.control_field_map.values()
            extra_control_fields = {k: deb['control_fields'][k] for k in keys}
            pulp2deb_to_save.append(
                Pulp2DebPackage(
                    checksumtype=deb['checksumtype'],
                    checksum=deb['checksum'],
                    filename=deb['filename'],
                    extra_control_fields=json.dumps(extra_control_fields),
                    pulp2content=pulp2_id_obj_map[deb['_id']],
                    size=deb['size'],
                    **pre_migrate_fields,
                )
            )

        cls.objects.bulk_create(
            pulp2deb_to_save,
            ignore_conflicts=True,
            batch_size=DEFAULT_BATCH_SIZE,
        )

    def create_pulp3_content(self):
        """
        Create a Pulp 3 detail Content unit for saving it later in a bulk operation.

        Return an unsaved Pulp 3 Content.
        """
        package_paragraph = deb822.Packages()

        object_dict = self.__dict__

        for cls_field, control_field in self.control_field_map.items():
            if object_dict[cls_field]:
                package_paragraph[control_field] = object_dict[cls_field]

        if self.extra_control_fields:
            extra_control_fields = json.loads(self.extra_control_fields)

            for control_field, value in extra_control_fields.items():
                package_paragraph[control_field] = value

        serializer = Package822Serializer.from822(data=package_paragraph)
        serializer.is_valid(raise_exception=True)

        pulp3_package = pulp3_models.Package(
            relative_path=self.filename,
            sha256=self.checksum,
            **serializer.validated_data,
        )

        return (pulp3_package, None)
