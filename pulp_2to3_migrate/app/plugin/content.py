import asyncio
import logging
import math
import os
import shutil

from django.db import transaction
from django.conf import settings

from pulpcore.app.models import storage
from pulpcore.plugin.models import (
    Artifact,
    ProgressReport,
)
from pulpcore.plugin.stages import (
    ArtifactSaver,
    ContentSaver,
    create_pipeline,
    DeclarativeArtifact,
    DeclarativeContent,
    EndStage,
    Stage,
    QueryExistingArtifacts,
    QueryExistingContents
)
from pulpcore.plugin.tasking import WorkingDirectory

from pulp_2to3_migrate.app.constants import NOT_USED
from pulp_2to3_migrate.app.models import Pulp2Content


_logger = logging.getLogger(__name__)


class DeclarativeContentMigration:
    """
    A pipeline that migrates pre-migrated Pulp 2 content into Pulp 3.

    The plugin writer needs to specify a first_stage that will create a
    :class:`~pulpcore.plugin.stages.DeclarativeContent` object for each Content unit that should
    be migrated to Pulp 3.
    """
    def __init__(self, first_stage):
        self.first_stage = first_stage

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
            RelatePulp2to3Content()
        ]

        return pipeline

    async def create(self):
        """
        Perform the work specified by pipeline.
        """
        with WorkingDirectory():  # TODO: Working Directory is probably not needed
            stages = self.pipeline_stages()
            stages.append(EndStage())
            pipeline = create_pipeline(stages)
            await pipeline


class ContentMigrationFirstStage(Stage):
    """
    The first stage of a content migration pipeline.

    Creates hard links (or copies) for Pulp 2 content and creates DeclarativeContent for content
    being migrated.
    """
    def __init__(self, model):
        """
        Args:
            model: The Pulp 2to3 detailed content model to be migrated
        """
        super().__init__()
        self.model = model

    async def create_artifact(self, pulp2_storage_path, expected_digests={}, expected_size=None):
        """
        Create a hard link if possible and then create an Artifact.

        If it's not possible to create a hard link, file is copied to the Pulp 3 storage.
        """
        if not expected_digests.get('sha256'):
            # TODO: all checksums are calculated for the pulp 2 storage path, is it ok?
            artifact = Artifact.init_and_validate(pulp2_storage_path, size=expected_size)

        sha256digest = expected_digests.get('sha256') or artifact.sha256

        pulp3_storage_relative_path = storage.get_artifact_path(sha256digest)
        pulp3_storage_path = os.path.join(settings.MEDIA_ROOT, pulp3_storage_relative_path)
        os.makedirs(os.path.dirname(pulp3_storage_path), exist_ok=True)

        is_copied = False
        try:
            os.link(pulp2_storage_path, pulp3_storage_path)
        except FileExistsError:
            pass
        except OSError:
            _logger.debug('Hard link cannot be created, file will be copied.')
            shutil.copy2(pulp2_storage_path, pulp3_storage_path)
            is_copied = True

        expected_digests = {'sha256': sha256digest}

        if is_copied:
            # recalculate checksums to ensure that after being copied a file is still fine
            artifact = Artifact.init_and_validate(file=pulp3_storage_path,
                                                  expected_digests=expected_digests,
                                                  expected_size=expected_size)
        else:
            # a hard link has been created or a file has already been in the pulp 3 storage, so
            # artifact's path can be just updated and no checksum recalculation is needed.
            artifact.file = pulp3_storage_path

        return artifact

    async def run(self):
        """
        Schedules multiple coroutines to migrate pre-migrated content to Pulp 3
        """
        content_type = self.model.type
        pulp2content_qs = Pulp2Content.objects.filter(pulp2_content_type_id=content_type,
                                                      pulp3_content=None)
        total_pulp2content = pulp2content_qs.count()

        # determine the batch size if we can have up to 36 coroutines and the number of batches (or
        # coroutines)
        max_coro = 36
        batch_size = 1
        if total_pulp2content > max_coro:
            batch_size = math.ceil(total_pulp2content / max_coro)
        batch_count = math.ceil(total_pulp2content / batch_size)

        with ProgressReport(
            message='Migrating {} content to Pulp 3'.format(content_type.upper()),
            code='migrating.{}.content'.format(content_type),
            total=total_pulp2content
        ) as pb:
            # schedule content migration
            migrators = []
            for batch_idx in range(batch_count):
                start = batch_idx * batch_size
                end = (batch_idx + 1) * batch_size
                batch = pulp2content_qs[start:end]
                migrators.append(self.migrate_to_pulp3(batch, pb=pb))

            if migrators:
                await asyncio.wait(migrators)

    async def migrate_to_pulp3(self, batch, pb=None):
        """
        A default implementation of DeclarativeContent creation for migrating content to Pulp 3.

        Plugin writers might want to override this method if it doesn't satisfy their needs as is.

        Args:
            batch: A batch of Pulp2Content objects to migrate to Pulp 3
        """
        for pulp2content in batch:
            pulp_2to3_detail_content = pulp2content.detail_model.get()
            pulp3content = pulp_2to3_detail_content.create_pulp3_content()
            future_relations = {'pulp2content': pulp2content}

            if not pulp2content.downloaded:
                # on_demand content is partially migrated - only Content is created at this stage.
                # Remote Artifact and Content Artifact should be created at the time of
                # importers/remotes migration. Rely on downloaded flag on Pulp2Content to
                # identify on_demand content.
                dc = DeclarativeContent(content=pulp3content)
            else:
                artifact = await self.create_artifact(pulp2content.pulp2_storage_path,
                                                      pulp_2to3_detail_content.expected_digests,
                                                      pulp_2to3_detail_content.expected_size)
                da = DeclarativeArtifact(
                    artifact=artifact,
                    url=NOT_USED,
                    relative_path=pulp_2to3_detail_content.relative_path_for_content_artifact,
                    remote=NOT_USED,
                    deferred_download=False)
                dc = DeclarativeContent(content=pulp3content, d_artifacts=[da])

            dc.extra_data = future_relations
            await self.put(dc)
            if pb:
                pb.increment()


class RelatePulp2to3Content(Stage):
    """
    Relates Pulp2Content and migrated Pulp 3 content.

    This relation signifies that the migration of this piece of content is done.
    Without this stage *all* the content will be migrated on every migration plan run.
    """
    async def run(self):
        """
        Saves the relation between Pulp2Content and migrated Pulp 3 content.

        Plugin writers have to provide the ``pulp2content`` in the ``extra_data`` attribute
        of a declarative Pulp 3 content.
        """
        async for batch in self.batches():
            pulp2content_batch = []
            with transaction.atomic():
                for d_content in batch:
                    pulp2content = d_content.extra_data.get('pulp2content')
                    pulp2content.pulp3_content = d_content.content.master
                    pulp2content_batch.append(pulp2content)

                pulp2content.__class__.objects.bulk_update(objs=pulp2content_batch,
                                                           fields=['pulp3_content'],
                                                           batch_size=1000)

            for d_content in batch:
                await self.put(d_content)
