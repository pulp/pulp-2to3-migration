
import asyncio
import json
from collections import OrderedDict

from django.db import transaction

from . import pulp2_models
from . import utils

from .pulp_2to3_models import (
    Pulp2Blob,
    Pulp2Manifest,
    Pulp2ManifestList,
    Pulp2Tag,
)

from .repository import DockerImporter, DockerDistributor
from pulp_container.app.models import (
    Blob,
    BlobManifest,
    ContainerRepository,
    Manifest,
    ManifestListManifest,
    Tag,
)

from pulp_2to3_migration.app.constants import NOT_USED
from pulp_2to3_migration.app.plugin.api import (
    ContentMigrationFirstStage,
    DeclarativeContentMigration,
    Pulp2to3PluginMigrator,
    RelatePulp2to3Content,
)
from pulpcore.plugin.stages import (
    ArtifactSaver,
    ContentSaver,
    DeclarativeArtifact,
    ResolveContentFutures,
    Stage,
    QueryExistingArtifacts,
    QueryExistingContents,
)


class DockerMigrator(Pulp2to3PluginMigrator):
    """
    An entry point for migration the Pulp 2 Docker plugin to Pulp 3.
    """
    pulp2_plugin = 'docker'
    pulp2_content_models = {
        'docker_blob': pulp2_models.Blob,
        'docker_manifest': pulp2_models.Manifest,
        'docker_manifest_list': pulp2_models.ManifestList,
        'docker_tag': pulp2_models.Tag,
    }
    pulp2_collection = 'units_docker_manifest'
    # will be renamed to pulp_container
    pulp3_plugin = 'pulp_container'
    pulp3_repository = ContainerRepository

    content_models = OrderedDict([
        ('docker_blob', Pulp2Blob),
        ('docker_manifest', Pulp2Manifest),
        ('docker_manifest_list', Pulp2ManifestList),
        ('docker_tag', Pulp2Tag),
    ])

    mutable_content_models = {
        'docker_tag': Pulp2Tag,
    }

    importer_migrators = {
        'docker_importer': DockerImporter,
    }
    distributor_migrators = {
        'docker_distributor_web': DockerDistributor,
    }

    premigrate_hook = {
        'docker_tag': utils.find_tags
    }

    artifactless_types = {
        'docker_tag': Pulp2Tag,
    }

    future_types = {
        'docker_manifest': pulp2_models.Manifest,
        'docker_manifest_list': pulp2_models.ManifestList
    }

    @classmethod
    def migrate_content_to_pulp3(cls):
        """
        Migrate pre-migrated Pulp 2 docker content.
        """
        first_stage = ContentMigrationFirstStage(cls)
        dm = DockerDeclarativeContentMigration(first_stage=first_stage)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(dm.create())


class DockerDeclarativeContentMigration(DeclarativeContentMigration):
    """
    A pipeline that migrates pre-migrated Pulp 2 docker content into Pulp 3.
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
            DockerContentSaver(),
            ResolveContentFutures(),
            InterrelateContent(),
            RelatePulp2to3Content(),
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
            manifestlist_manifest_batch = []
            blob_manifest_batch = []
            manifest_batch = []
            with transaction.atomic():
                for dc in batch:
                    if dc.extra_data.get('man_rel'):
                        thru = self.relate_manifest_to_list(dc)
                        manifestlist_manifest_batch.extend(thru)
                    elif dc.extra_data.get('blob_rel'):
                        thru = self.relate_blob(dc)
                        blob_manifest_batch.extend(thru)

                    if dc.extra_data.get('config_blob_rel'):
                        manifest_to_update = self.relate_config_blob(dc)
                        manifest_batch.append(manifest_to_update)

                ManifestListManifest.objects.bulk_create(objs=manifestlist_manifest_batch,
                                                         ignore_conflicts=True,
                                                         batch_size=1000)
                BlobManifest.objects.bulk_create(objs=blob_manifest_batch,
                                                 ignore_conflicts=True,
                                                 batch_size=1000)

                Manifest.objects.bulk_update(objs=manifest_batch,
                                             fields=['config_blob'],
                                             batch_size=1000)
            for dc in batch:
                await self.put(dc)

    def relate_config_blob(self, dc):
        """
        Relate a Blob to a Manifest as a config layer.

        Args:
            dc (pulpcore.plugin.stages.DeclarativeContent): dc for a Manifest
        """
        configured_dc_id = dc.extra_data.get('config_blob_rel')
        # find blob by id
        # We are relying on the order of the processed DC
        # Blobs should have passed through ContentSaver stage already
        blob = Blob.objects.filter(digest=configured_dc_id).first()
        dc.content.config_blob = blob
        return dc.content

    def relate_blob(self, dc):
        """
        Relate a Blob to a Manifest.

        Args:
            dc (pulpcore.plugin.stages.DeclarativeContent): dc for a Manifest
        """
        related_dc_id_list = dc.extra_data.get('blob_rel')
        # find blob by id
        # We are relying on the order of the processed DC
        # Blobs should have passed through ContentSaver stage already
        blob_list = Blob.objects.filter(digest__in=related_dc_id_list)
        thru = []
        for blob in blob_list:
            thru.append(BlobManifest(manifest=dc.content, manifest_blob=blob))
        return thru

    def relate_manifest_to_list(self, dc):
        """
        Relate an ImageManifest to a ManifestList.

        Args:
            dc (pulpcore.plugin.stages.DeclarativeContent): dc for a Manifest list
        """
        related_dc_id_list = dc.extra_data.get('man_rel')
        # find manifests by id
        # We are relying on the order of the processed DC
        # Manifests should have passed through ContentSaver stage already
        man_list = Manifest.objects.filter(digest__in=related_dc_id_list)
        # read json file to revieve platfrom data
        with dc.content._artifacts.get().file.open() as content_file:
            raw = content_file.read()
        content_data = json.loads(raw)
        manifests_from_json = content_data['manifests']

        mlm = []
        for manifest in manifests_from_json:
            digest = manifest['digest']
            for item in man_list:
                if item.digest == digest:
                    break
            platform = manifest['platform']
            thru = ManifestListManifest(manifest_list=item, image_manifest=dc.content,
                                        architecture=platform['architecture'],
                                        os=platform['os'],
                                        features=platform.get('features', ''),
                                        variant=platform.get('variant', ''),
                                        os_version=platform.get('os.version', ''),
                                        os_features=platform.get('os.features', '')
                                        )
            mlm.append(thru)

        return mlm


class DockerContentSaver(ContentSaver):
    """
    Stage for saving DC.
    """

    async def _pre_save(self, batch):
        """
        Relate manifest to tag before saving tag.
        We need to do it in the pre_save hook because of Tag's uniqueness constraint.

        Args:
            batch (list of :class:`~pulpcore.plugin.stages.DeclarativeContent`): The batch of
                :class:`~pulpcore.plugin.stages.DeclarativeContent` objects to be saved.

        """
        for dc in batch:
            if type(dc.content) == Tag:
                related_man_id = dc.extra_data.get('tag_rel')
                # find manifest by id
                # We are relying on the order of the processed DC
                # Manifests should have passed through ContentSaver stage already
                man = Manifest.objects.filter(digest=related_man_id).first()
                artifact = man._artifacts.get()
                # add manifest's artifact
                da = DeclarativeArtifact(
                    artifact=artifact,
                    url=NOT_USED,
                    relative_path=dc.content.name,
                    remote=NOT_USED,
                    deferred_download=False)
                dc.d_artifacts.append(da)
                dc.content.tagged_manifest = man
