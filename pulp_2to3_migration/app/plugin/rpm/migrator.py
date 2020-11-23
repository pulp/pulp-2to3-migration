import asyncio

from django.db import transaction
from django.db.models import Q

from collections import OrderedDict

from pulp_2to3_migration.app.constants import DEFAULT_BATCH_SIZE
from pulp_2to3_migration.app.plugin.api import (
    ContentMigrationFirstStage,
    DeclarativeContentMigration,
    Pulp2to3PluginMigrator,
    RelatePulp2to3Content,
    UpdateLCEs,
)

from pulp_rpm.app.models import (
    Modulemd,
    Package,
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
        'rpm': pulp2_models.RPM,
        'srpm': pulp2_models.SRPM,
        'distribution': pulp2_models.Distribution,
        'erratum': pulp2_models.Errata,
        'modulemd': pulp2_models.Modulemd,
        'modulemd_defaults': pulp2_models.ModulemdDefaults,
        'yum_repo_metadata_file': pulp2_models.YumMetadataFile,
        'package_langpacks': pulp2_models.PackageLangpacks,
        'package_group': pulp2_models.PackageGroup,
        'package_category': pulp2_models.PackageCategory,
        'package_environment': pulp2_models.PackageEnvironment,
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
    def migrate_content_to_pulp3(cls, skip_corrupted=False):
        """
        Migrate pre-migrated Pulp 2 RPM plugin content.

        Args:
            skip_corrupted (bool): If True, corrupted content is skipped during migration,
                                   no task failure.

        """
        first_stage = ContentMigrationFirstStage(cls, skip_corrupted=skip_corrupted)
        dm = RpmDeclarativeContentMigration(first_stage=first_stage)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(dm.create())


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
            UpdateLCEs(),
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

            with transaction.atomic():
                for dc in batch:
                    if type(dc.content) == Modulemd:
                        thru = self.relate_packages_to_module(dc)
                        modulemd_packages_batch.extend(thru)

                ModulemdPackages = Modulemd.packages.through
                ModulemdPackages.objects.bulk_create(objs=modulemd_packages_batch,
                                                     ignore_conflicts=True,
                                                     batch_size=DEFAULT_BATCH_SIZE)

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
            packages_list = Package.objects.filter(pq).only(
                'pk', 'name', 'epoch', 'version', 'release', 'arch'
            ).iterator()

        thru = []
        # keep track of rpm nevra for which we already created a relation with module.
        # it can happen that we have 2 rpms with same nevra but different checksum
        # in that case just skip the second occurrence of rpm and do not create the relation
        already_related = []
        for pkg in packages_list:
            nevra = pkg.nevra
            if nevra not in already_related:
                thru.append(ModulemdPackages(package_id=pkg.pk, modulemd_id=module_dc.content.pk))
                already_related.append(nevra)
        return thru
