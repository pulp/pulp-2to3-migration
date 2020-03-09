from bson import BSON
from collections import defaultdict

from django.contrib.postgres.fields import JSONField
from django.db import models

from pulp_2to3_migration.app.models import Pulp2to3Content

from pulp_rpm.app.models import (
    Modulemd,
    ModulemdDefaults,
    Package,
    RepoMetadataFile,
    UpdateRecord,
)

from . import pulp2_models

from .xml_utils import get_cr_obj


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
        pulp2_content_batch = pulp2_models.RPM.objects.filter(id__in=pulp2_ids).as_pymongo().only(
            'name',
            'epoch',
            'version',
            'release',
            'arch',
            'checksum',
            'checksumtype',
            'repodata',
            'is_modular',
            'size',
            'filename',
            'pk',
        )
        import gzip

        pulp2rpm_to_save = []
        for rpm in pulp2_content_batch:
            compressed_repodata = rpm['repodata']
            decompressed_repodata = {}
            for name, gzipped_data in compressed_repodata.items():
                decompressed_repodata[name] = gzip.zlib.decompress(
                    bytearray(gzipped_data)).decode()
            rpm['repodata'] = decompressed_repodata

            pulp2rpm_to_save.append(
                cls(name=rpm['name'],
                    epoch=rpm['epoch'],
                    version=rpm['version'],
                    release=rpm['release'],
                    arch=rpm['arch'],
                    checksum=rpm['checksum'],
                    checksumtype=rpm['checksumtype'],
                    repodata=rpm['repodata'],
                    is_modular=rpm['is_modular'],
                    size=rpm['size'],
                    filename=rpm['filename'],
                    pulp2content=pulp2_id_obj_map[rpm['_id']])
            )
        cls.objects.bulk_create(pulp2rpm_to_save, ignore_conflicts=True)

    async def create_pulp3_content(self):
        """
        Create a Pulp 3 Package content for saving it later in a bulk operation.
        """
        cr_package = await get_cr_obj(self)
        pkg_dict = Package.createrepo_to_dict(cr_package)
        pkg_dict['is_modular'] = self.is_modular
        return Package(**pkg_dict)


class Pulp2Erratum(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store Pulp2 Errata content details.

    Relations:
        pulp2content(models.ManyToManyField): relation to the generic model. It needs to be
                                              many-to-many because multiple Pulp2Content can
                                              refer to the same detail model of errata.

    """

    # Required fields
    errata_id = models.TextField()
    updated = models.TextField()
    repo_id = models.TextField()

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
    set_pulp2_repo = True

    class Meta:
        unique_together = ('errata_id', 'repo_id')
        default_related_name = 'erratum_detail_model'

    @classmethod
    async def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 Erratum content with all the fields needed to create a Pulp 3 Package.

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.

        """
        def get_pkglist(errata_id):
            """
            Get a pkglist for a specified erratum.

            In Pulp 2 many pkglists are present for each erratum, including duplicated ones.
            The aggregation pipeline generates unique collections grouped by module info.

            Ported from Pulp 2 Errata serializer
            https://github.com/pulp/pulp_rpm/blob/91145f24afed19812e3b53805c2bfd69fd24764a/plugins/pulp_rpm/plugins/serializers.py#L53

            Args:
                errata_id(str): Id of an erratum to get a pkglist for
            """
            match_stage = {'$match': {'errata_id': errata_id}}
            unwind_collections_stage = {'$unwind': '$collections'}
            unwind_packages_stage = {'$unwind': '$collections.packages'}

            # Group all packages by their relation to a module specified in each collection.
            # All non-modular RPMs will be in a single collection.
            group_stage = {'$group': {'_id': '$collections.module',
                                      'packages': {'$addToSet': '$collections.packages'}}}
            collections = pulp2_models.ErratumPkglist.objects.aggregate(
                match_stage, unwind_collections_stage, unwind_packages_stage, group_stage,
                allowDiskUse=True)

            pkglist = []
            for collection_idx, collection in enumerate(collections):
                # To preserve the original format of a pkglist the 'short' and 'name'
                # keys are added. 'short' can be an empty string, collection 'name'
                # should be unique within an erratum.
                item = {'packages': collection['packages'],
                        'short': '',
                        'name': 'collection-%s' % collection_idx}
                if collection['_id']:
                    item['module'] = collection['_id']
                pkglist.append(item)
            return pkglist

        pulp2_id_obj_map = defaultdict(dict)
        pulp2erratum_to_save = []
        for pulp2content in content_batch:
            repo_id = pulp2content.pulp2_repo.pk
            pulp2_id_obj_map[pulp2content.pulp2_id][repo_id] = pulp2content
        pulp2_ids = pulp2_id_obj_map.keys()
        pulp2_erratum_content_batch = pulp2_models.Errata.objects.filter(id__in=pulp2_ids)
        for erratum in pulp2_erratum_content_batch:
            for repo_id, pulp2content in pulp2_id_obj_map[erratum.id].items():
                pulp2erratum_to_save.append(
                    cls(errata_id=erratum.errata_id,
                        updated=erratum.updated,
                        repo_id=repo_id,
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
                        pkglist=get_pkglist(erratum.errata_id),
                        title=erratum.title,
                        solution=erratum.solution,
                        summary=erratum.summary,
                        pulp2content=pulp2content))
        cls.objects.bulk_create(pulp2erratum_to_save, ignore_conflicts=True)

    async def create_pulp3_content(self):
        """
        Create a Pulp 3 Advisory content for saving it later in a bulk operation.
        """

        # TODO: figure out
        #    - how to split back merged errata into multiple ones

        cr_update = {}  # Create creterepo_c update record based on pulp2 data
        relations = {}  # TODO: UpdateCollection and UpdateReference
        # digest = hash_update_record(cr_update)
        advisory = UpdateRecord(**cr_update)
        # advisory.digest = digest
        return advisory, relations


class Pulp2YumRepoMetadataFile(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store pulp 2 yum_repo_metadata_file
    content details for Pulp 3 content creation.
    """
    data_type = models.CharField(max_length=20)
    checksum = models.CharField(max_length=128)
    checksum_type = models.CharField(max_length=6)
    repo_id = models.TextField()

    pulp2_type = 'yum_repo_metadata_file'

    class Meta:
        unique_together = ('data_type', 'repo_id', 'pulp2content')
        default_related_name = 'yum_repo_metadata_file_detail_model'

    @property
    def expected_digests(self):
        """Return expected digests."""
        return {self.checksum_type: self.checksum}

    @property
    def expected_size(self):
        """Return expected size."""
        return

    @property
    def relative_path_for_content_artifact(self):
        """Return relative path."""
        return self.data_type

    @classmethod
    async def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 YumMetadataFile with all the fields needed to create a Pulp 3 content

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.

        """
        pulp2_id_obj_map = {pulp2content.pulp2_id: pulp2content for pulp2content in content_batch}
        pulp2_ids = pulp2_id_obj_map.keys()
        pulp2_metadata_content_batch = pulp2_models.YumMetadataFile.objects.filter(id__in=pulp2_ids)
        pulp2metadata_to_save = [cls(data_type=meta.data_type,
                                     checksum=meta.checksum,
                                     checksum_type=meta.checksum_type,
                                     repo_id=meta.repo_id,
                                     pulp2content=pulp2_id_obj_map[meta.id])
                                 for meta in pulp2_metadata_content_batch]
        cls.objects.bulk_create(pulp2metadata_to_save, ignore_conflicts=True)

    async def create_pulp3_content(self):
        """
        Create a Pulp 3 RepoMetadataFile unit for saving it later in a bulk operation.
        """
        return RepoMetadataFile(data_type=self.data_type,
                                checksum=self.checksum,
                                checksum_type=self.checksum_type)


class Pulp2Modulemd(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store Pulp2 Modulemd content details.
    """

    # Unit key fields
    name = models.TextField()
    stream = models.TextField()
    version = models.BigIntegerField()
    context = models.TextField()
    arch = models.TextField()

    artifacts = JSONField()
    checksum = models.TextField()
    dependencies = JSONField()

    pulp2_type = 'modulemd'

    class Meta:
        unique_together = (
            'name', 'stream', 'version', 'context', 'arch', 'pulp2content')
        default_related_name = 'modulemd_detail_model'

    @property
    def expected_digests(self):
        """Return expected digests."""
        return {'sha256': self.checksum}

    @property
    def expected_size(self):
        """Return expected size."""
        return

    @property
    def relative_path_for_content_artifact(self):
        """Return relative path."""
        relative_path = '{}{}{}{}{}snippet'.format(
                        self.name, self.stream, self.version,
                        self.context, self.arch)

        return relative_path

    @classmethod
    async def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 modulemd content with all the fields needed to create a Pulp 3 content.

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.

        """
        pulp2_id_obj_map = {pulp2content.pulp2_id: pulp2content for pulp2content in content_batch}
        pulp2_ids = pulp2_id_obj_map.keys()
        pulp2_content_batch = pulp2_models.Modulemd.objects.filter(id__in=pulp2_ids)
        pulp2modules_to_save = [
            cls(name=md.name,
                stream=md.stream,
                version=md.version,
                context=md.context,
                arch=md.arch,
                dependencies=md.dependencies,
                artifacts=md.artifacts,
                checksum=md.checksum,
                pulp2content=pulp2_id_obj_map[md.id])
            for md in pulp2_content_batch]
        cls.objects.bulk_create(pulp2modules_to_save, ignore_conflicts=True)

    async def create_pulp3_content(self):
        """
        Create a Pulp 3 Module content for saving it later in a bulk operation.
        """
        return Modulemd(name=self.name, stream=self.stream, version=self.version,
                        context=self.context, arch=self.arch, artifacts=self.artifacts,
                        dependencies=self.dependencies)


class Pulp2ModulemdDefaults(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store Pulp2 ModulemdDefaults content details.
    """

    # Unit key fields
    module = models.TextField()
    stream = models.TextField()
    profiles = JSONField(dict)
    digest = models.TextField()
    repo_id = models.TextField()

    pulp2_type = 'modulemd_defaults'

    class Meta:
        unique_together = ('digest', 'repo_id', 'pulp2content')
        default_related_name = 'modulemd_defaults_detail_model'

    @property
    def expected_digests(self):
        """Return expected digests."""
        return {'sha256': self.digest}

    @property
    def expected_size(self):
        """Return expected size."""
        return

    @property
    def relative_path_for_content_artifact(self):
        """Return relative path."""
        relative_path = '{}{}snippet'.format(self.module, self.stream)

        return relative_path

    @classmethod
    async def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 defaults content with all the fields needed to create a Pulp 3 content.

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.

        """

        def _get_profiles(profiles):
            """
            Out of incoming string create a bson string and decode it
            """

            bson_string = BSON(profiles, encoding='utf8')
            return bson_string.decode()

        pulp2_id_obj_map = {pulp2content.pulp2_id: pulp2content for pulp2content in content_batch}
        pulp2_ids = pulp2_id_obj_map.keys()
        pulp2_content_batch = pulp2_models.ModulemdDefaults.objects.filter(id__in=pulp2_ids)
        pulp2defaults_to_save = [
            cls(module=defaults.name,
                stream=defaults.stream,
                profiles=_get_profiles(defaults.profiles),
                digest=defaults.checksum,
                repo_id=defaults.repo_id,
                pulp2content=pulp2_id_obj_map[defaults.id])
            for defaults in pulp2_content_batch]
        cls.objects.bulk_create(pulp2defaults_to_save, ignore_conflicts=True)

    async def create_pulp3_content(self):
        """
        Create a Pulp 3 Module content for saving it later in a bulk operation.
        """
        return ModulemdDefaults(module=self.module, stream=self.stream,
                                profiles=self.profiles, digest=self.digest)
