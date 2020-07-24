import os

from bson import BSON
from collections import defaultdict

import createrepo_c as cr

from django.contrib.postgres.fields import JSONField
from django.db import models

from pulp_2to3_migration.app.models import (
    Pulp2to3Content,
    Pulp2RepoContent
)

from pulp_rpm.app.comps import dict_digest
from pulp_rpm.app.advisory import hash_update_record
from pulp_rpm.app.models import (
    DistributionTree,
    Modulemd,
    ModulemdDefaults,
    Package,
    PackageCategory,
    PackageEnvironment,
    PackageGroup,
    PackageLangpacks,
    RepoMetadataFile,
    UpdateCollection,
    UpdateCollectionPackage,
    UpdateRecord,
    UpdateReference,
)

from pulp_rpm.app.kickstart.treeinfo import (
    PulpTreeInfo,
    TreeinfoData
)

from . import pulp2_models

from .comps_utils import (
    langpacks_to_libcomps,
    pkg_cat_to_libcomps,
    pkg_env_to_libcomps,
    pkg_grp_to_libcomps
)

from .erratum import (
    get_bool,
    get_datetime,
    get_package_checksum,
    get_pulp2_filtered_collections
)
from .xml_utils import (
    decompress_repodata,
    get_cr_obj,
)

SRPM_UNIT_FIELDS = set([
    'name',
    'epoch',
    'version',
    'release',
    'arch',
    'checksum',
    'checksumtype',
    'repodata',
    'size',
    'filename',
    'pk',
])

RPM_UNIT_FIELDS = SRPM_UNIT_FIELDS | set(['is_modular'])


class Pulp2RpmBase(Pulp2to3Content):
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
    size = models.BigIntegerField()
    filename = models.TextField()

    class Meta:
        abstract = True

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
        Pre-migrate Pulp 2 RPM content with all the fields needed to create a Pulp 3 Package.

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.

        """
        pulp2_id_obj_map = {pulp2content.pulp2_id: pulp2content for pulp2content in content_batch}
        pulp2_ids = pulp2_id_obj_map.keys()
        pulp2_content_batch = cls.pulp2_model.objects.filter(id__in=pulp2_ids).as_pymongo().only(
            *cls.unit_fields)
        pulp2rpm_to_save = []
        for rpm in pulp2_content_batch:
            rpm['repodata'] = decompress_repodata(rpm['repodata'])

            pulp2rpm_to_save.append(
                cls(name=rpm['name'],
                    epoch=rpm['epoch'],
                    version=rpm['version'],
                    release=rpm['release'],
                    arch=rpm['arch'],
                    checksum=rpm['checksum'],
                    checksumtype=rpm['checksumtype'],
                    repodata=rpm['repodata'],
                    is_modular=rpm.get('is_modular', False),
                    size=rpm['size'],
                    filename=rpm['filename'],
                    pulp2content=pulp2_id_obj_map[rpm['_id']])
            )
        cls.objects.bulk_create(pulp2rpm_to_save, ignore_conflicts=True)

    def create_pulp3_content(self):
        """
        Create a Pulp 3 Package content for saving it later in a bulk operation.
        """
        cr_package = get_cr_obj(self)
        pkg_dict = Package.createrepo_to_dict(cr_package)
        pkg_dict['is_modular'] = self.is_modular
        return (Package(**pkg_dict), None)


class Pulp2Rpm(Pulp2RpmBase):
    """
    Pulp 2to3 detail content model to store Pulp 2 RPM content details for Pulp 3 content creation.
    """

    unit_fields = RPM_UNIT_FIELDS
    pulp2_model = pulp2_models.RPM

    pulp2_type = 'rpm'

    class Meta:
        unique_together = (
            'name', 'epoch', 'version', 'release', 'arch', 'checksumtype', 'checksum',
            'pulp2content')
        default_related_name = 'rpm_detail_model'


class Pulp2Srpm(Pulp2RpmBase):
    """
    Pulp 2to3 detail content model to store Pulp 2 SRPM content details for Pulp 3 content creation.
    """

    unit_fields = SRPM_UNIT_FIELDS
    pulp2_model = pulp2_models.SRPM

    pulp2_type = 'srpm'

    class Meta:
        unique_together = (
            'name', 'epoch', 'version', 'release', 'arch', 'checksumtype', 'checksum',
            'pulp2content')
        default_related_name = 'srpm_detail_model'


class Pulp2Erratum(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store Pulp2 Errata content details.

    """
    # Required fields
    errata_id = models.TextField()
    updated = models.TextField()
    repo_id = models.TextField()

    issued = models.TextField(null=True)
    status = models.TextField(null=True)
    description = models.TextField(null=True)
    pushcount = models.TextField(null=True)
    references = JSONField()
    reboot_suggested = models.BooleanField()
    relogin_suggested = models.BooleanField()
    restart_suggested = models.BooleanField()
    errata_from = models.TextField(null=True)
    severity = models.TextField(null=True)
    rights = models.TextField(null=True)
    version = models.TextField(null=True)
    release = models.TextField(null=True)
    errata_type = models.TextField(null=True)
    pkglist = JSONField()
    title = models.TextField(null=True)
    solution = models.TextField(null=True)
    summary = models.TextField(null=True)

    pulp2_type = 'erratum'
    set_pulp2_repo = True
    cached_repo_data = {}

    class Meta:
        unique_together = ('errata_id', 'repo_id')
        default_related_name = 'erratum_detail_model'

    @classmethod
    def get_repo_data(cls, pulp2_repo):
        """
        Get content data of a repository, NEVRA of packages and NSVCA of modules.

        Args:
            pulp2_repo(Pulp2Repository): a pre-migrated repo to collect data from

        Returns:
            dict: {'packages': list of NEVRA tuples of the packages which are in this repo,
                   'modules': list of NSVCA tuples of the module which are in this repo}

        """
        if pulp2_repo.pk in cls.cached_repo_data:
            return cls.cached_repo_data[pulp2_repo.pk]

        repo_pkg_nevra = []
        repo_module_nsvca = []

        # gather info about available packages
        package_pulp2_ids = Pulp2RepoContent.objects.filter(
            pulp2_repository=pulp2_repo,
            pulp2_content_type_id='rpm'
        ).only('pulp2_unit_id').values_list('pulp2_unit_id', flat=True)

        pulp2rpms = Pulp2Rpm.objects.filter(pulp2content__pulp2_id__in=package_pulp2_ids)
        for pkg in pulp2rpms.iterator():
            repo_pkg_nevra.append((pkg.name, pkg.epoch or '0', pkg.version, pkg.release, pkg.arch))

        # gather info about available modules
        modulemd_pulp2_ids = Pulp2RepoContent.objects.filter(
            pulp2_repository=pulp2_repo,
            pulp2_content_type_id='modulemd'
        ).only('pulp2_unit_id').values_list('pulp2_unit_id', flat=True)

        pulp2modulemds = Pulp2Modulemd.objects.filter(pulp2content__pulp2_id__in=modulemd_pulp2_ids)
        for module in pulp2modulemds.iterator():
            repo_module_nsvca.append((module.name, module.stream, module.version, module.context,
                                      module.arch))

        # data for only one repo is cached (it should be enough, because content is ordered by
        # a repo it belongs to)
        cls.cached_repo_data.clear()
        cls.cached_repo_data[pulp2_repo.pk] = {
            'packages': repo_pkg_nevra,
            'modules': repo_module_nsvca
        }
        return cls.cached_repo_data[pulp2_repo.pk]

    @classmethod
    def pre_migrate_content_detail(cls, content_batch):
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

    def get_collections(self):
        """
        Get collections with the relevant packages to the repo this erratum belongs to.

        """
        repo_data = Pulp2Erratum.get_repo_data(self.pulp2content.pulp2_repo)
        return get_pulp2_filtered_collections(
            self,
            repo_data['packages'],
            repo_data['modules']
        )

    def create_pulp3_content(self):
        """
        Create a Pulp 3 Advisory content for saving it later in a bulk operation.
        """
        rec = cr.UpdateRecord()
        rec.fromstr = self.errata_from
        rec.status = self.status
        rec.type = self.errata_type
        rec.version = self.version
        rec.id = self.errata_id
        rec.title = self.title
        rec.issued_date = get_datetime(self.issued)
        rec.updated_date = get_datetime(self.updated)
        rec.rights = self.rights
        rec.summary = self.summary
        rec.description = self.description
        rec.reboot_suggested = get_bool(self.reboot_suggested)
        rec.severity = self.severity
        rec.solution = self.solution
        rec.release = self.release
        rec.pushcount = self.pushcount

        collections = self.get_collections()
        for collection in collections:
            col = cr.UpdateCollection()
            col.shortname = collection.get('short')
            col.name = collection.get('name')
            module = collection.get('module')
            if module:
                col.module = cr.UpdateCollectionModule(**module)

            for package in collection.get('packages', []):
                pkg = cr.UpdateCollectionPackage()
                pkg.name = package['name']
                pkg.version = package['version']
                pkg.release = package['release']
                pkg.epoch = package['epoch']
                pkg.arch = package['arch']
                pkg.src = package.get('src')
                pkg.filename = package['filename']
                pkg.reboot_suggested = get_bool(package.get('reboot_suggested'))
                pkg.restart_suggested = get_bool(package.get('restart_suggested'))
                pkg.relogin_suggested = get_bool(package.get('relogin_suggested'))
                checksum_tuple = get_package_checksum(package)
                if checksum_tuple:
                    pkg.sum_type, pkg.sum = checksum_tuple
                col.append(pkg)

            rec.append_collection(col)

        for reference in self.references:
            ref = cr.UpdateReference()
            ref.href = reference.get('href')
            ref.id = reference.get('id')
            ref.type = reference.get('type')
            ref.title = reference.get('title')
            rec.append_reference(ref)

        update_record = UpdateRecord(**UpdateRecord.createrepo_to_dict(rec))
        update_record.digest = hash_update_record(rec)
        relations = {'collections': defaultdict(list), 'references': []}

        for collection in rec.collections:
            coll_dict = UpdateCollection.createrepo_to_dict(collection)
            coll = UpdateCollection(**coll_dict)

            for package in collection.packages:
                pkg_dict = UpdateCollectionPackage.createrepo_to_dict(package)
                pkg = UpdateCollectionPackage(**pkg_dict)
                relations['collections'][coll].append(pkg)

        for reference in rec.references:
            reference_dict = UpdateReference.createrepo_to_dict(reference)
            ref = UpdateReference(**reference_dict)
            relations['references'].append(ref)

        return (update_record, relations)


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
        path = self.pulp2content.pulp2_storage_path
        metadata_file_name = os.path.basename(path)
        return os.path.join('repodata', metadata_file_name)

    @classmethod
    def pre_migrate_content_detail(cls, content_batch):
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

    def create_pulp3_content(self):
        """
        Create a Pulp 3 RepoMetadataFile unit for saving it later in a bulk operation.
        """
        return (RepoMetadataFile(data_type=self.data_type,
                                 checksum=self.checksum,
                                 checksum_type=self.checksum_type), None)


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
    def pre_migrate_content_detail(cls, content_batch):
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

    def create_pulp3_content(self):
        """
        Create a Pulp 3 Module content for saving it later in a bulk operation.
        """
        return (Modulemd(name=self.name, stream=self.stream, version=self.version,
                         context=self.context, arch=self.arch, artifacts=self.artifacts,
                         dependencies=self.dependencies), None)


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
    def pre_migrate_content_detail(cls, content_batch):
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

    def create_pulp3_content(self):
        """
        Create a Pulp 3 Module content for saving it later in a bulk operation.
        """
        return (ModulemdDefaults(module=self.module, stream=self.stream,
                                 profiles=self.profiles, digest=self.digest), None)


class Pulp2Distribution(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store Pulp2 Distribution content details.
    """

    # Unit key fields
    distribution_id = models.TextField()
    family = models.TextField()
    variant = models.TextField()
    version = models.TextField()
    arch = models.TextField()

    pulp2_type = "distribution"

    filename = None

    class Meta:
        unique_together = (
            'distribution_id', 'family', 'variant', 'version', 'arch', 'pulp2content')
        default_related_name = 'distribution_detail_model'

    @property
    def relative_path_for_content_artifact(self):
        """Return relative path."""
        return self.filename

    @classmethod
    def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 Distribution content with all the fields needed to create a Pulp 3
        DistributionTree.

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.

        """
        pulp2_id_obj_map = {pulp2content.pulp2_id: pulp2content for pulp2content in content_batch}
        pulp2_ids = pulp2_id_obj_map.keys()
        pulp2_distribution_content_batch = pulp2_models.Distribution.objects.filter(
            id__in=pulp2_ids)
        pulp2distribution_to_save = [
            cls(distribution_id=distribution.distribution_id,
                family=distribution.family,
                variant=distribution.variant,
                version=distribution.version,
                arch=distribution.arch,
                pulp2content=pulp2_id_obj_map[distribution.id])
            for distribution in pulp2_distribution_content_batch]
        cls.objects.bulk_create(pulp2distribution_to_save, ignore_conflicts=True)

    def create_pulp3_content(self):
        """
        Create a Pulp 3 Distribution content for saving later in a bulk operation.
        """
        namespaces = [".treeinfo", "treeinfo"]
        for namespace in namespaces:
            treeinfo = PulpTreeInfo()
            try:
                treeinfo.load(f=os.path.join(self.pulp2content.pulp2_storage_path, '.treeinfo'))
            except FileNotFoundError:
                continue
            self.filename = namespace
            treeinfo_parsed = treeinfo.parsed_sections()
            treeinfo_serialized = TreeinfoData(treeinfo_parsed).to_dict(filename=namespace)
            # Pulp 2 only knows about the top level kickstart repository
            treeinfo_serialized["repositories"] = {'.': None}
            # Pulp 2 did not support addon repositories, so we should not list them here either
            treeinfo_serialized['addons'] = {}
            # Pulp 2 only supported variants that are in the root of the repository
            variants = {}
            for name, variant in treeinfo_serialized['variants'].items():
                if variant['repository'] == '.':
                    variants[name] = variant
            treeinfo_serialized['variants'] = variants
            # Reset build_timestamp so Pulp will fetch all the addons during the next sync
            treeinfo_serialized['distribution_tree']['build_timestamp'] = 0
            return (DistributionTree(**treeinfo_serialized["distribution_tree"]),
                    treeinfo_serialized)


class Pulp2PackageLangpacks(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store pulp 2 package_langpacks
    content details for Pulp 3 content creation.
    """
    matches = JSONField()
    repo_id = models.TextField()

    pulp2_type = 'package_langpacks'

    class Meta:
        unique_together = ('repo_id', 'pulp2content')
        default_related_name = 'package_langpacks_detail_model'

    @classmethod
    def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 langpacks content with all the fields needed to create a Pulp 3 content.

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.

        """
        pulp2_id_obj_map = {pulp2content.pulp2_id: pulp2content for pulp2content in content_batch}
        pulp2_ids = pulp2_id_obj_map.keys()
        pulp2_content_batch = pulp2_models.PackageLangpacks.objects.filter(id__in=pulp2_ids)
        pulp2langpacks_to_save = [
            cls(repo_id=p.repo_id,
                matches=p.matches,
                pulp2content=pulp2_id_obj_map[p.id])
            for p in pulp2_content_batch]
        cls.objects.bulk_create(pulp2langpacks_to_save, ignore_conflicts=True)

    def create_pulp3_content(self):
        """
        Create a Pulp 3 Package Langpacks content for saving it later in a bulk operation.
        """
        langpacks = langpacks_to_libcomps(self)
        langpacks_dict = PackageLangpacks.libcomps_to_dict(langpacks)
        return (PackageLangpacks(matches=langpacks_dict['matches'],
                                 digest=dict_digest(langpacks_dict)), None)


class Pulp2PackageGroup(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store pulp 2 package_group
    content details for Pulp 3 content creation.
    """
    package_group_id = models.TextField()
    repo_id = models.TextField()

    default = models.BooleanField()
    user_visible = models.BooleanField()
    display_order = models.IntegerField(null=True)
    name = models.TextField()
    description = models.TextField()
    # This field contains mandatory, default, optional, conditional packages
    packages = JSONField()
    desc_by_lang = JSONField(dict)
    name_by_lang = JSONField(dict)
    biarch_only = models.BooleanField(default=False)

    pulp2_type = 'package_group'

    class Meta:
        unique_together = ('repo_id', 'package_group_id', 'pulp2content')
        default_related_name = 'package_group_detail_model'

    @classmethod
    def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 package groups with all the fields needed to create a Pulp 3 content.

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.

        """
        def _get_packages(group):
            """Merge in a list all package types"""
            # order of type of packages is important and should be preserved
            return [(3, group.mandatory_package_names), (0, group.default_package_names),
                    (1, group.optional_package_names), (2, group.conditional_package_names)]

        pulp2_id_obj_map = {pulp2content.pulp2_id: pulp2content for pulp2content in content_batch}
        pulp2_ids = pulp2_id_obj_map.keys()
        pulp2_content_batch = pulp2_models.PackageGroup.objects.filter(id__in=pulp2_ids)
        pulp2groups_to_save = [
            cls(repo_id=p.repo_id,
                package_group_id=p.package_group_id,
                default=p.default,
                user_visible=p.user_visible,
                display_order=p.display_order,
                name=p.name,
                description=p.description if p.description else '',
                packages=_get_packages(p),
                desc_by_lang=p.translated_description,
                name_by_lang=p.translated_name,
                pulp2content=pulp2_id_obj_map[p.id])
            for p in pulp2_content_batch]
        cls.objects.bulk_create(pulp2groups_to_save, ignore_conflicts=True)

    def create_pulp3_content(self):
        """
        Create a Pulp 3 Package Group content for saving it later in a bulk operation.
        """
        group = pkg_grp_to_libcomps(self)
        group_dict = PackageGroup.libcomps_to_dict(group)
        packages = group_dict['packages']
        # ugly stuff
        for pkg in packages:
            pkg['requires'] = pkg['requires'] or None
        group_dict['digest'] = dict_digest(group_dict)
        return (PackageGroup(**group_dict), None)


class Pulp2PackageCategory(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store pulp 2 package_category
    content details for Pulp 3 content creation.
    """
    package_category_id = models.TextField()
    repo_id = models.TextField()

    display_order = models.IntegerField(null=True)
    name = models.TextField()
    description = models.TextField()
    packagegroupids = JSONField()
    desc_by_lang = JSONField(dict)
    name_by_lang = JSONField(dict)

    pulp2_type = 'package_category'

    class Meta:
        unique_together = ('repo_id', 'package_category_id', 'pulp2content')
        default_related_name = 'package_category_detail_model'

    @classmethod
    def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 package category with all the fields needed to create a Pulp 3 content.

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.

        """
        pulp2_id_obj_map = {pulp2content.pulp2_id: pulp2content for pulp2content in content_batch}
        pulp2_ids = pulp2_id_obj_map.keys()
        pulp2_content_batch = pulp2_models.PackageCategory.objects.filter(id__in=pulp2_ids)
        pulp2groups_to_save = [
            cls(repo_id=p.repo_id,
                package_category_id=p.package_category_id,
                display_order=p.display_order,
                name=p.name,
                description=p.description if p.description else '',
                packagegroupids=p.packagegroupids,
                desc_by_lang=p.translated_description,
                name_by_lang=p.translated_name,
                pulp2content=pulp2_id_obj_map[p.id])
            for p in pulp2_content_batch]
        cls.objects.bulk_create(pulp2groups_to_save, ignore_conflicts=True)

    def create_pulp3_content(self):
        """
        Create a Pulp 3 Package Category content for saving it later in a bulk operation.
        """
        cat = pkg_cat_to_libcomps(self)
        category_dict = PackageCategory.libcomps_to_dict(cat)
        category_dict['digest'] = dict_digest(category_dict)
        return (PackageCategory(**category_dict), None)


class Pulp2PackageEnvironment(Pulp2to3Content):
    """
    Pulp 2to3 detail content model to store pulp 2 package_environment
    content details for Pulp 3 content creation.
    """
    package_environment_id = models.TextField()
    repo_id = models.TextField()

    display_order = models.IntegerField(null=True)
    name = models.TextField()
    description = models.TextField()
    group_ids = JSONField()
    option_ids = JSONField()
    desc_by_lang = JSONField(default=dict)
    name_by_lang = JSONField(default=dict)

    pulp2_type = 'package_environment'

    class Meta:
        unique_together = ('repo_id', 'package_environment_id', 'pulp2content')
        default_related_name = 'package_environment_detail_model'

    @classmethod
    def pre_migrate_content_detail(cls, content_batch):
        """
        Pre-migrate Pulp 2 package env. with all the fields needed to create a Pulp 3 content.

        Args:
             content_batch(list of Pulp2Content): pre-migrated generic data for Pulp 2 content.

        """
        pulp2_id_obj_map = {pulp2content.pulp2_id: pulp2content for pulp2content in content_batch}
        pulp2_ids = pulp2_id_obj_map.keys()
        pulp2_content_batch = pulp2_models.PackageEnvironment.objects.filter(id__in=pulp2_ids)
        pulp2envs_to_save = [
            cls(repo_id=p.repo_id,
                package_environment_id=p.package_environment_id,
                display_order=p.display_order,
                name=p.name,
                description=p.description if p.description else '',
                group_ids=p.group_ids,
                option_ids=p.options,
                desc_by_lang=p.translated_description,
                name_by_lang=p.translated_name,
                pulp2content=pulp2_id_obj_map[p.id])
            for p in pulp2_content_batch]
        cls.objects.bulk_create(pulp2envs_to_save, ignore_conflicts=True)

    def create_pulp3_content(self):
        """
        Create a Pulp 3 Package Environment content for saving it later in a bulk operation.
        """
        env = pkg_env_to_libcomps(self)
        environment_dict = PackageEnvironment.libcomps_to_dict(env)
        environment_dict['digest'] = dict_digest(environment_dict)
        return (PackageEnvironment(**environment_dict), None)
