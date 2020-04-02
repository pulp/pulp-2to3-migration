from django.db import transaction
from django.db.models import Q

from collections import OrderedDict

from pulp_2to3_migration.app.plugin.api import (
    ContentMigrationFirstStage,
    DeclarativeContentMigration,
    Pulp2to3PluginMigrator,
    RelatePulp2to3Content,
)

from pulp_rpm.app.models import (
    Modulemd,
    Package,
    PackageCategory,
    PackageEnvironment,
    PackageGroup,
    RpmRepository,
)
from pulp_rpm.app.tasks.synchronizing import RpmContentSaver

from . import pulp2_models

from .pulp_2to3_models import (
    Pulp2Distribution,
    Pulp2Erratum,
    Pulp2Modulemd,
    Pulp2ModulemdDefaults,
    Pulp2PackageCategory,
    Pulp2PackageEnvironment,
    Pulp2PackageGroup,
    Pulp2PackageLangpacks,
    Pulp2Rpm,
    Pulp2Srpm,
    Pulp2YumRepoMetadataFile,
)

from .repository import (
    RpmDistributor,
    RpmImporter,
)

from pulpcore.plugin.stages import (
    ArtifactSaver,
    RemoteArtifactSaver,
    ResolveContentFutures,
    Stage,
    QueryExistingArtifacts,
    QueryExistingContents,
)

from . import package_utils
from pulp_2to3_migration.app.models import (
    Pulp2Content,
    Pulp2RepoContent,
    Pulp2Repository,
)


class RpmMigrator(Pulp2to3PluginMigrator):
    """
    An entry point for migration the Pulp 2 RPM plugin to Pulp 3.

    Attributes:
        pulp2_plugin(str): Pulp 2 plugin name
        pulp2_content_models(dict): {'pulp2 content_type_id': 'content class to access MongoDB'}
        pulp2_collection(str): a pulp2 collection which existence signifies that a plugin
                               is installed in pulp2
        pulp3_plugin(str): Pulp 3 plugin name
        content_models(dict): {'pulp2 content_type_id': 'detail content class to pre-migrate to'}
        importer_migrators(dict): {'importer_type_id': 'pulp_2to3 importer interface/migrator'}

    """
    pulp2_plugin = 'rpm'
    pulp2_content_models = {
        'distribution': pulp2_models.Distribution,
        'erratum': pulp2_models.Errata,
        'modulemd': pulp2_models.Modulemd,
        'modulemd_defaults': pulp2_models.ModulemdDefaults,
        'package_category': pulp2_models.PackageCategory,
        'package_environment': pulp2_models.PackageEnvironment,
        'package_group': pulp2_models.PackageGroup,
        'package_langpacks': pulp2_models.PackageLangpacks,
        'rpm': pulp2_models.RPM,
        'srpm': pulp2_models.SRPM,
    }
    pulp2_collection = 'units_rpm'
    pulp3_plugin = 'pulp_rpm'
    pulp3_repository = RpmRepository
    content_models = OrderedDict([
        ('rpm', Pulp2Rpm),
        ('srpm', Pulp2Srpm),
        ('distribution', Pulp2Distribution),
        ('erratum', Pulp2Erratum),
        ('modulemd', Pulp2Modulemd),
        ('modulemd_defaults', Pulp2ModulemdDefaults),
        ('yum_repo_metadata_file', Pulp2YumRepoMetadataFile),
        ('package_langpacks', Pulp2PackageLangpacks),
        ('package_group', Pulp2PackageGroup),
        ('package_category', Pulp2PackageCategory),
        ('package_environment', Pulp2PackageEnvironment),
    ])
    mutable_content_models = {
        'erratum': Pulp2Erratum,
        'modulemd': Pulp2Modulemd,
        'modulemd_defaults': Pulp2ModulemdDefaults,
    }
    importer_migrators = {
        'yum_importer': RpmImporter,
    }
    distributor_migrators = {
        'yum_distributor': RpmDistributor,
    }
    lazy_types = {
        'distribution': Pulp2Distribution,
        'rpm': Pulp2Rpm,
        'srpm': Pulp2Srpm,
    }
    future_types = {
        'rpm': Pulp2Rpm,
        'package_group': Pulp2PackageGroup,
        'package_category': Pulp2PackageCategory,
    }
    artifactless_types = {
        'erratum': Pulp2Erratum,
        'package_langpacks': Pulp2PackageLangpacks,
        'package_group': Pulp2PackageGroup,
        'package_category': Pulp2PackageCategory,
        'package_environment': Pulp2PackageEnvironment,
    }
    multi_artifact_types = {
        'distribution': Pulp2Distribution
    }

    @classmethod
    async def migrate_content_to_pulp3(cls):
        """
        Migrate pre-migrated Pulp 2 RPM plugin content.
        """
        first_stage = ContentMigrationFirstStage(cls)
        dm = RpmDeclarativeContentMigration(first_stage=first_stage)
        await dm.create()


class RpmDeclarativeContentMigration(DeclarativeContentMigration):
    """
    A pipeline that migrates pre-migrated Pulp 2 rpm content into Pulp 3.
    """

    def pipeline_stages(self):
        """
        Build a list of stages.

        This defines the "architecture" of the content migration to Pulp 3.

        Returns:
            list: List of :class:`~pulpcore.plugin.stages.Stage` instances

        """
        pipeline = [
            self.first_stage,
            QueryExistingArtifacts(),
            ArtifactSaver(),
            QueryExistingContents(),
            RpmContentSaver(),
            RemoteArtifactSaver(),
            InterrelateContent(),
            RelatePulp2to3Content(),
            ResolveContentFutures(),
        ]

        return pipeline


class InterrelateContent(Stage):
    """
    Stage for relating Content to other Content.
    """

    async def run(self):
        """
        Relate each item in the input queue to objects specified on the DeclarativeContent.
        """
        async for batch in self.batches():
            modulemd_packages_batch = []
            group_packages_batch = []
            category_groups_batch = []
            environment_groups_batch = []
            environment_options_batch = []
            with transaction.atomic():
                for dc in batch:
                    if type(dc.content) == Modulemd:
                        thru = self.relate_packages_to_module(dc)
                        modulemd_packages_batch.extend(thru)
                    elif type(dc.content) == PackageGroup:
                        thru = self.relate_packages_to_group(dc)
                        group_packages_batch.extend(thru)
                    elif type(dc.content) == PackageCategory:
                        thru = self.relate_groups_to_category(dc)
                        category_groups_batch.extend(thru)
                    elif type(dc.content) == PackageEnvironment:
                        groups_thru, options_thru = self.relate_groups_to_environment(dc)
                        environment_groups_batch.extend(groups_thru)
                        environment_options_batch.extend(groups_thru)

                ModulemdPackages = Modulemd.packages.through
                ModulemdPackages.objects.bulk_create(objs=modulemd_packages_batch,
                                                     ignore_conflicts=True,
                                                     batch_size=1000)
                PackageGroupPackages = PackageGroup.related_packages.through
                PackageGroupPackages.objects.bulk_create(objs=group_packages_batch,
                                                         ignore_conflicts=True,
                                                         batch_size=1000)
                PackageCategoryGroups = PackageCategory.packagegroups.through
                PackageCategoryGroups.objects.bulk_create(objs=category_groups_batch,
                                                          ignore_conflicts=True,
                                                          batch_size=1000)
                PackageEnvironmentGroups = PackageEnvironment.packagegroups.through
                PackageEnvironmentGroups.objects.bulk_create(objs=environment_groups_batch,
                                                             ignore_conflicts=True,
                                                             batch_size=1000)
                PackageEnvOptGroups = PackageEnvironment.optionalgroups.through
                PackageEnvOptGroups.objects.bulk_create(objs=environment_options_batch,
                                                        ignore_conflicts=True,
                                                        batch_size=1000)

            for dc in batch:
                await self.put(dc)

    def relate_packages_to_module(self, module_dc):
        """
        Relate Packages to a Module.

        Args:
            module_dc (pulpcore.plugin.stages.DeclarativeContent): dc for a Module
        """
        ModulemdPackages = Modulemd.packages.through
        artifacts_list = module_dc.content.artifacts
        # find rpm by nevra
        # We are relying on the order of the processed DC
        # RPMs should have passed through ContentSaver stage already
        pq = Q()
        for artifact in artifacts_list:
            nevra = package_utils.nevra(artifact)
            pq |= Q(
                name=nevra[0],
                epoch=nevra[1],
                version=nevra[2],
                release=nevra[3],
                arch=nevra[4],
                is_modular=True)
        packages_list = []
        if pq:
            packages_list = Package.objects.filter(pq).only('pk').iterator()

        thru = []
        # keep track of rpm nevra for which we already created a relation with module.
        # it can happen that we have 2 rpms with same nevra but different checksum
        # in that case just skip the second occurrence of rpm and do not create the relation
        already_related = []
        for pkg in packages_list:
            if pkg.nevra not in already_related:
                thru.append(ModulemdPackages(package_id=pkg.pk, modulemd_id=module_dc.content.pk))
                already_related.append(pkg.nevra)
        return thru

    def relate_packages_to_group(self, group_dc):
        """
        Relate Packages to a Group.

        Args:
            module_dc (pulpcore.plugin.stages.DeclarativeContent): dc for a PackageGroup
        """
        PackageGroupPackages = PackageGroup.related_packages.through
        packages = group_dc.content.packages
        package_list = [pkg['name'] for pkg in packages]
        pulp2_repo_id = group_dc.extra_data.get('pulp2_repo_id')
        pulp2_repo = Pulp2Repository.objects.get(pulp2_repo_id=pulp2_repo_id)
        # all pulp2 unit_ids for rpm within the pulp2repo
        filters = dict(pulp2_repository=pulp2_repo,
                       pulp2_content_type_id__in=['rpm', 'srpm'])

        unit_ids = Pulp2RepoContent.objects.filter(**filters).values_list(
            'pulp2_unit_id', flat=True).iterator()
        # all pulp3 rpm pks within the pulp2repo
        pulp3_content = Pulp2Content.objects.filter(pulp2_id__in=unit_ids).only(
            'pulp3_content').values_list('pulp3_content__pk', flat=True).iterator()
        pulp3_packages = Package.objects.filter(
            name__in=package_list,
            pk__in=pulp3_content).only('pk').values_list('pk', flat=True).iterator()
        thru = []
        for pkg in pulp3_packages:
            thru.append(PackageGroupPackages(package_id=pkg, packagegroup_id=group_dc.content.pk))
        return thru

    def relate_groups_to_category(self, category_dc):
        """
        Relate groups to a Category

        Args:
            module_dc (pulpcore.plugin.stages.DeclarativeContent): dc for a PackageCategory
        """
        PackageCategoryGroups = PackageCategory.packagegroups.through
        groups = category_dc.content.group_ids
        group_list = [grp['name'] for grp in groups]
        pulp2_repo_id = category_dc.extra_data.get('pulp2_repo_id')
        pulp2_repo = Pulp2Repository.objects.get(pulp2_repo_id=pulp2_repo_id)
        # all pulp2 unit_ids for groups within the pulp2repo
        unit_ids = Pulp2RepoContent.objects.filter(
            pulp2_repository=pulp2_repo,
            pulp2_content_type_id='package_group').values_list(
            'pulp2_unit_id', flat=True).iterator()
        # all pulp3 groups pks within the pulp2repo
        pulp3_content = Pulp2Content.objects.filter(pulp2_id__in=unit_ids).only(
            'pulp3_content').values_list('pulp3_content__pk', flat=True).iterator()
        pulp3_groups = PackageGroup.objects.filter(
            id__in=group_list,
            pk__in=pulp3_content).only('pk').values_list('pk', flat=True).iterator()
        thru = []
        for grp in pulp3_groups:
            thru.append(PackageCategoryGroups(packagegroup_id=grp,
                                              packagecategory_id=category_dc.content.pk))
        return thru

    def relate_groups_to_environment(self, env_dc):
        """
        Relate groups to a Environment

        Args:
            module_dc (pulpcore.plugin.stages.DeclarativeContent): dc for a PackageCategory
        """
        PackageEnvGroups = PackageEnvironment.packagegroups.through
        PackageEnvOptGroups = PackageEnvironment.optionalgroups.through
        groups = env_dc.content.group_ids
        options = env_dc.content.option_ids
        group_list = [grp['name'] for grp in groups]
        option_list = [opt['name'] for opt in options]
        pulp2_repo_id = env_dc.extra_data.get('pulp2_repo_id')
        pulp2_repo = Pulp2Repository.objects.get(pulp2_repo_id=pulp2_repo_id)
        # all pulp2 unit_ids for groups within the pulp2repo
        unit_ids = Pulp2RepoContent.objects.filter(
            pulp2_repository=pulp2_repo,
            pulp2_content_type_id='package_group').values_list(
            'pulp2_unit_id', flat=True).iterator()
        # all pulp3 groups pks within the pulp2repo
        pulp3_content = Pulp2Content.objects.filter(pulp2_id__in=unit_ids).only(
            'pulp3_content').values_list('pulp3_content__pk', flat=True).iterator()
        pulp3_groups = PackageGroup.objects.filter(
            id__in=group_list + option_list,
            pk__in=pulp3_content).only('pk', 'id').iterator()
        group_thru = []
        option_thru = []
        for grp in pulp3_groups:
            if grp.id in group_list:
                group_thru.append(PackageEnvGroups(packagegroup_id=grp.pk,
                                                   packageenvironment_id=env_dc.content.pk))
            elif grp.id in option_list:
                option_thru.append(PackageEnvOptGroups(packagegroup_id=grp.pk,
                                                       packageenvironment_id=env_dc.content.pk))
        return group_thru, option_thru
