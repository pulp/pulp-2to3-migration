import logging

from django.db import transaction
from django.db.models import Q

from collections import OrderedDict

from pulp_2to3_migration.app.plugin.api import (
    ContentMigrationFirstStage,
    DeclarativeContentMigration,
    Pulp2to3PluginMigrator,
    RelatePulp2to3Content,
)

from pulp_rpm.app import models as pulp3_models

from .pulp2_models import (
    Errata,
    Modulemd,
    ModulemdDefaults,
    PackageCategory,
    PackageGroup,
    PackageEnvironment,
    PackageLangpacks,
    RPM,
    YumMetadataFile,
)
from .pulp_2to3_models import (
    Pulp2Erratum,
    Pulp2Modulemd,
    Pulp2ModulemdDefaults,
    Pulp2PackageCategory,
    Pulp2PackageEnvironment,
    Pulp2PackageGroup,
    Pulp2PackageLangpacks,
    Pulp2Rpm,
    Pulp2YumRepoMetadataFile,
)

from .repository import (
    RpmDistributor,
    RpmImporter,
)
from pulpcore.plugin.stages import (
    ArtifactSaver,
    ContentSaver,
    RemoteArtifactSaver,
    ResolveContentFutures,
    Stage,
    QueryExistingArtifacts,
    QueryExistingContents,
)

from . import package_utils


_logger = logging.getLogger(__name__)


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
        'rpm': RPM,
        'erratum': Errata,
        'modulemd': Modulemd,
        'modulemd_defaults': ModulemdDefaults,
        'yum_repo_metadata_file': YumMetadataFile,
        'package_langpacks': PackageLangpacks,
        'package_group': PackageGroup,
        'package_category': PackageCategory,
        'package_environment': PackageEnvironment,
    }
    pulp2_collection = 'units_rpm'
    pulp3_plugin = 'pulp_rpm'
    pulp3_repository = pulp3_models.RpmRepository
    content_models = OrderedDict([
        ('rpm', Pulp2Rpm),
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
        'rpm': Pulp2Rpm,
    }
    future_types = {
        'rpm': Pulp2Rpm,
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
            ContentSaver(),
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
            with transaction.atomic():
                for dc in batch:
                    if type(dc.content) == pulp3_models.Modulemd:
                        thru = self.relate_packages_to_module(dc)
                        modulemd_packages_batch.extend(thru)

                ModulemdPackages = pulp3_models.Modulemd.packages.through
                ModulemdPackages.objects.bulk_create(objs=modulemd_packages_batch,
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
        ModulemdPackages = pulp3_models.Modulemd.packages.through
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
            packages_list = pulp3_models.Package.objects.filter(pq).only('pk')
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
