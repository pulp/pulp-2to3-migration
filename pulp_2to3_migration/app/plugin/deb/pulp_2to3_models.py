import logging
import json

from debian import deb822
from hashlib import sha256

from django.db import models as django_models

from pulp_deb.app import models as pulp3_models
from pulp_deb.app.serializers import Package822Serializer

from pulp_2to3_migration.app.constants import DEFAULT_BATCH_SIZE
from pulp_2to3_migration.app.models import (
    Pulp2to3Content,
    Pulp2Content,
)

from . import pulp2_models

_logger = logging.getLogger(__name__)


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


class Pulp2DebRelease(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store pulp 2 DebRelease content details for Pulp 3
    content creation.
    """
    pulp2_type = 'deb_release'
    distribution = django_models.TextField()
    codename = django_models.TextField()
    suite = django_models.TextField(null=True)

    class Meta:
        default_related_name = 'deb_release_detail_model'
        unique_together = ('codename', 'suite', 'distribution')

    @classmethod
    def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 content with all the fields needed to create a Pulp 3 Content

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.
        """
        pulp2_unit_map = {pulp2unit.pulp2_id: pulp2unit for pulp2unit in content_batch}
        pulp2_ids = pulp2_unit_map.keys()
        pulp2_unit_batch = pulp2_models.DebRelease.objects.filter(id__in=pulp2_ids)
        units_to_save = [Pulp2DebRelease(distribution=release.distribution,
                                         codename=release.codename,
                                         suite=release.suite,
                                         pulp2content=pulp2_unit_map[release.id],)
                         for release in pulp2_unit_batch]

        cls.objects.bulk_create(
            units_to_save,
            ignore_conflicts=True,
            batch_size=DEFAULT_BATCH_SIZE
        )

    def create_pulp3_content(self):
        """
        Create a Pulp 3 detail Content unit for saving it later in a bulk operation.

        Return an unsaved Pulp 3 Content
        """
        pulp3_release = pulp3_models.Release(
            distribution=self.distribution.strip("/"),
            codename=self.codename,
            suite=self.suite,
        )

        return (pulp3_release, None)


class Pulp2DebComponent(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store pulp 2 DebComponent content details for Pulp 3
    content creation.
    """
    pulp2_type = 'deb_component'
    distribution = django_models.TextField()
    codename = django_models.TextField()
    component = django_models.TextField()
    suite = django_models.TextField()

    class Meta:
        default_related_name = 'deb_component_detail_model'
        unique_together = ('component', 'codename', 'suite', 'distribution')

    @classmethod
    def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 content with all the fields needed to create a Pulp 3 Content

        Note that this pre_migrated_content_detail method will not just create
        Pulp2DebComponent entries, but also Pulp2DebComponentPackage entries,
        and Pulp2DebReleaseArchitecture entries, since they are all created from the same
        Pulp 2 type (DebComponent).

        For each Pulp2DebComponentPackage and each Pulp2DebComponent there will also be an
        additional Pulp2Content created. Such Pulp2Content will have the same pulp2_id as
        the original, but with a different pulp2_subid. That way we can record the one to
        many Pulp 2 to Pulp 3 mapping later.

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.
        """
        pulp2_unit_map = {pulp2unit.pulp2_id: pulp2unit for pulp2unit in content_batch}
        pulp2_ids = pulp2_unit_map.keys()
        pulp2_unit_batch = pulp2_models.DebComponent.objects.filter(id__in=pulp2_ids)
        component_units_to_save = []
        component_package_units_to_save = []
        release_architecture_units_to_save = []
        pulp2_sub_records_to_save = []

        for component_unit in pulp2_unit_batch:
            pulp2_base_record = pulp2_unit_map[component_unit.id]
            distribution = component_unit.distribution
            codename = component_unit.release
            component = component_unit.name
            release = pulp2_models.DebRelease.objects.filter(
                repoid=component_unit.repoid,
                distribution=distribution,
            ).first()
            suite = release.suite
            component_units_to_save.append(Pulp2DebComponent(
                distribution=distribution,
                codename=codename,
                component=component,
                suite=suite,
                pulp2content=pulp2_base_record,
            ))
            architectures = set()
            for package_id in component_unit.packages:
                package_unit = pulp2_models.DebPackage.objects.filter(id__in=[package_id]).first()
                package_relative_path = package_unit.filename
                package_sha256 = package_unit.checksum

                # We are using the sha256 of the concatenated unique_together fields for the subid:
                pulp2_subid_string = (suite + codename + distribution + component
                                      + package_relative_path + package_sha256)
                pulp2_subid = sha256(pulp2_subid_string.encode('utf-8')).hexdigest()

                pulp2_sub_record = Pulp2Content(
                    pulp2_subid=pulp2_subid,
                    pulp2_id=pulp2_base_record.pulp2_id,
                    pulp2_content_type_id=pulp2_base_record.pulp2_content_type_id,
                    pulp2_last_updated=pulp2_base_record.pulp2_last_updated,
                    pulp2_storage_path=pulp2_base_record.pulp2_storage_path,
                    downloaded=pulp2_base_record.downloaded,
                )
                _logger.debug('Adding Pulp2Content subrecord {}'.format(pulp2_sub_record))
                pulp2_sub_records_to_save.append(pulp2_sub_record)

                component_package_units_to_save.append(Pulp2DebComponentPackage(
                    package_relative_path=package_relative_path,
                    package_sha256=package_sha256,
                    component=component,
                    distribution=distribution,
                    codename=codename,
                    suite=suite,
                    pulp2content=pulp2_sub_record,
                ))
                architectures.add(package_unit.architecture)

            architectures.discard('all')
            for architecture in architectures:
                # We are using the sha256 of the concatenated unique_together fields for the subid:
                pulp2_subid_string = architecture + distribution + codename + suite
                pulp2_subid = sha256(pulp2_subid_string.encode('utf-8')).hexdigest()

                pulp2_sub_record = Pulp2Content(
                    pulp2_subid=pulp2_subid,
                    pulp2_id=pulp2_base_record.pulp2_id,
                    pulp2_content_type_id=pulp2_base_record.pulp2_content_type_id,
                    pulp2_last_updated=pulp2_base_record.pulp2_last_updated,
                    pulp2_storage_path=pulp2_base_record.pulp2_storage_path,
                    downloaded=pulp2_base_record.downloaded,
                )
                _logger.debug('Adding Pulp2Content subrecord {}'.format(pulp2_sub_record))
                pulp2_sub_records_to_save.append(pulp2_sub_record)

                release_architecture_units_to_save.append(Pulp2DebReleaseArchitecture(
                    architecture=architecture,
                    distribution=distribution,
                    codename=codename,
                    suite=suite,
                    pulp2content=pulp2_sub_record,
                ))

        Pulp2Content.objects.bulk_create(
            pulp2_sub_records_to_save,
            ignore_conflicts=True,
            batch_size=DEFAULT_BATCH_SIZE
        )
        cls.objects.bulk_create(
            component_units_to_save,
            ignore_conflicts=True,
            batch_size=DEFAULT_BATCH_SIZE
        )
        Pulp2DebComponentPackage.objects.bulk_create(
            component_package_units_to_save,
            ignore_conflicts=True,
            batch_size=DEFAULT_BATCH_SIZE
        )
        Pulp2DebReleaseArchitecture.objects.bulk_create(
            release_architecture_units_to_save,
            ignore_conflicts=True,
            batch_size=DEFAULT_BATCH_SIZE
        )

    def create_pulp3_content(self):
        """
        Create a Pulp 3 detail Content unit for saving it later in a bulk operation.

        Return an unsaved Pulp 3 Content
        """
        release = pulp3_models.Release.objects.filter(
            distribution=self.distribution,
            codename=self.codename,
            suite=self.suite,
        ).first()
        pulp3_component = pulp3_models.ReleaseComponent(
            component=self.component,
            release=release,
        )
        return (pulp3_component, None)


class Pulp2DebComponentPackage(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store pulp 2 DebComponent content details for Pulp 3
    content creation.
    """
    pulp2_type = 'deb_component'
    package_relative_path = django_models.TextField()
    package_sha256 = django_models.TextField()
    component = django_models.TextField()
    distribution = django_models.TextField()
    codename = django_models.TextField()
    suite = django_models.TextField()

    class Meta:
        default_related_name = 'deb_component_package_detail_model'
        unique_together = (
            'package_relative_path',
            'package_sha256',
            'component',
            'distribution',
            'codename',
            'suite',
        )

    @classmethod
    def pre_migrate_content_detail(cls, content_batch):
        """
        This function does not do anything, since the relevant DB entries are already
        created by the pre_migrated_content_detail method from the Pulp2DebComponent
        class. This is so, because both types are created from the same Pulp 2 content.
        """
        pass

    def create_pulp3_content(self):
        """
        Create a Pulp 3 detail Content unit for saving it later in a bulk operation.

        Return an unsaved Pulp 3 Content
        """
        release_component = pulp3_models.ReleaseComponent.objects.filter(
            component=self.component,
            release__distribution=self.distribution,
            release__codename=self.codename,
            release__suite=self.suite,
        ).first()
        package = pulp3_models.Package.objects.filter(
            relative_path=self.package_relative_path,
            sha256=self.package_sha256,
        ).first()
        pulp3_package_release_component = pulp3_models.PackageReleaseComponent(
            release_component=release_component,
            package=package,
        )
        return (pulp3_package_release_component, None)


class Pulp2DebReleaseArchitecture(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store pulp 2 DebComponent content details for Pulp 3
    content creation.
    """
    pulp2_type = 'deb_component'
    architecture = django_models.TextField()
    distribution = django_models.TextField()
    codename = django_models.TextField()
    suite = django_models.TextField()

    class Meta:
        default_related_name = 'deb_release_architecture_detail_model'
        unique_together = ('architecture', 'distribution', 'codename', 'suite')

    @classmethod
    def pre_migrate_content_detail(cls, content_batch):
        """
        This function does not do anything, since the relevant DB entries are already
        created by the pre_migrated_content_detail method from the Pulp2DebComponent
        class. This is so, because both types are created from the same Pulp 2 content.
        """
        pass

    def create_pulp3_content(self):
        """
        Create a Pulp 3 detail Content unit for saving it later in a bulk operation.

        Return an unsaved Pulp 3 Content
        """
        release = pulp3_models.Release.objects.filter(
            distribution=self.distribution,
            codename=self.codename,
            suite=self.suite,
        ).first()
        pulp3_release_architecture = pulp3_models.ReleaseArchitecture(
            architecture=self.architecture,
            release=release,
        )
        return (pulp3_release_architecture, None)
