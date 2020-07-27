import asyncio
import functools
import logging
import os
import shutil
from urllib.parse import urljoin

from gettext import gettext as _

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

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
    QueryExistingArtifacts,
    QueryExistingContents,
    RemoteArtifactSaver,
    Stage,
)

from pulp_2to3_migration.app.constants import NOT_USED
from pulp_2to3_migration.app.models import (
    Pulp2Importer,
    Pulp2LazyCatalog,
)

_logger = logging.getLogger(__name__)


class DeclarativeContentMigration:
    """
    A pipeline that migrates pre-migrated Pulp 2 content into Pulp 3.

    The plugin writer needs to specify a first_stage that will create a
    :class:`~pulpcore.plugin.stages.DeclarativeContent` object for each Content unit that should
    be migrated to Pulp 3.
    """

    def __init__(self, first_stage):
        """Initializes DeclarativeContentMigration."""
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
            RemoteArtifactSaver(),
            UpdateLCEs(),
            RelatePulp2to3Content()
        ]

        return pipeline

    async def create(self):
        """
        Perform the work specified by pipeline.
        """
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

    def __init__(self, migrator):
        """
        Args:
            migrator: A plugin migrator to be used
        """
        super().__init__()
        self.migrator = migrator

    async def create_artifact(self, pulp2_storage_path, expected_digests={}, expected_size=None,
                              downloaded=True):
        """
        Create a hard link if possible and then create an Artifact.

        If it's not possible to create a hard link, file is copied to the Pulp 3 storage.
        For non-downloaded content, artifact with its expected checksum and size is created.
        """
        if not downloaded:
            if not expected_digests:
                raise ValueError(_('No digest is provided for on_demand content creation. Pulp 2 '
                                   'storage path: {}'.format(pulp2_storage_path)))
            artifact = Artifact(**expected_digests)
            artifact.size = expected_size
            return artifact

        artifact = Artifact.init_and_validate(pulp2_storage_path,
                                              expected_digests=expected_digests,
                                              expected_size=expected_size)

        pulp3_storage_relative_path = storage.get_artifact_path(artifact.sha256)
        pulp3_storage_path = os.path.join(settings.MEDIA_ROOT, pulp3_storage_relative_path)
        os.makedirs(os.path.dirname(pulp3_storage_path), exist_ok=True)

        is_copied = False
        try:
            os.link(pulp2_storage_path, pulp3_storage_path)
        except FileExistsError:
            pass
        except OSError:
            _logger.debug(_('Hard link cannot be created, file will be copied.'))
            shutil.copy2(pulp2_storage_path, pulp3_storage_path)
            is_copied = True

        if not expected_digests:
            expected_digests = {'sha256': artifact.sha256}

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

        It migrates content type by type.
        If a plugin needs to have more control over the order of content migration, it should
        override this method.
        """
        for ctype, cmodel in self.migrator.content_models.items():
            # we need to go through all lazy content in case any of Remotes changed
            if ctype in self.migrator.lazy_types:
                pulp_2to3_detail_qs = cmodel.objects.all()
            else:
                pulp_2to3_detail_qs = cmodel.objects.filter(pulp2content__pulp3_content=None)

            # order by pulp2_repo if it's set
            if cmodel.set_pulp2_repo:
                pulp_2to3_detail_qs = pulp_2to3_detail_qs.order_by(
                    'repo_id').prefetch_related('pulp2content')
            else:
                pulp_2to3_detail_qs = pulp_2to3_detail_qs.prefetch_related('pulp2content')
            total_pulp_2to3_detail_content = pulp_2to3_detail_qs.count()

            with ProgressReport(
                message='Migrating {} content to Pulp 3 {}'.format(self.migrator.pulp2_plugin,
                                                                   ctype),
                code='migrating.{}.content'.format(self.migrator.pulp2_plugin),
                total=total_pulp_2to3_detail_content
            ) as pb:
                # We are waiting on the coroutine to finish, because the order of the processed
                # content for plugins like Container and RPM is important because of the relations
                # between the content types.
                await asyncio.gather(
                    self.migrate_to_pulp3(pulp_2to3_detail_qs, self.migrator, ctype, pb=pb)
                )

    async def migrate_to_pulp3(self, batch, migrator, content_type, pb=None):
        """
        A default implementation of DeclarativeContent creation for migrating content to Pulp 3.

        Plugin writers might want to override this method if it doesn't satisfy their needs as is.

        In this implementation there is an assumption that each content has one artifact.

        Args:
            batch: A batch of Pulp2Content objects to migrate to Pulp 3
            migrator: A plugin migrator to be used
            content_type: type of pulp2 content that is being mirated
        """
        @functools.lru_cache(maxsize=20)
        def get_remote_by_importer_id(importer_id):
            """
            Args:
                importer_id(str): Id of an importer in Pulp 2

            Returns:
                remote(pulpcore.app.models.Remote): A corresponding remote in Pulp 3

            """
            try:
                pulp2importer = Pulp2Importer.objects.get(pulp2_object_id=importer_id)
            except ObjectDoesNotExist:
                return
            return pulp2importer.pulp3_remote

        futures = []
        batch_size = 1000
        is_lazy_type = content_type in migrator.lazy_types
        is_artifactless_type = content_type in migrator.artifactless_types
        has_future = content_type in migrator.future_types
        is_multi_artifact = content_type in migrator.multi_artifact_types

        for pulp_2to3_detail_content in batch.iterator():
            dc = None
            pulp2content = pulp_2to3_detail_content.pulp2content
            # only content that supports on_demand download can have entries in LCE
            if is_lazy_type:
                # get all Lazy Catalog Entries (LCEs) for this content
                pulp2lazycatalog = Pulp2LazyCatalog.objects.filter(
                    pulp2_unit_id=pulp2content.pulp2_id, is_migrated=False)

            lazy_wo_catalog = is_lazy_type and not pulp2lazycatalog
            if pulp2content.pulp3_content is not None and (not is_lazy_type or lazy_wo_catalog):
                if pb:
                    pb.total -= 1
                    pb.save()
                continue
            if is_lazy_type and not pulp2content.downloaded and not pulp2lazycatalog:
                _logger.warn(_('On_demand content cannot be migrated without an entry in the '
                               'lazy catalog, pulp2 unit_id: '
                               '{}'.format(pulp2content.pulp2_id)))
                continue

            if pulp2content.pulp3_content is not None and is_lazy_type and pulp2lazycatalog:
                # find already created pulp3 content
                pulp3content = pulp2content.pulp3_content
                extra_info = None

            else:
                # create pulp3 content and assign relations if present
                pulp3content, extra_info = pulp_2to3_detail_content.create_pulp3_content()
            future_relations = {'pulp2content': pulp2content}
            if extra_info:
                future_relations.update(extra_info)

            if is_multi_artifact:
                d_artifacts = []
                base_path = pulp2content.pulp2_storage_path
                remotes = set()
                future_relations.update({'lces': []})
                for image_relative_path in extra_info['download']['images']:
                    image_path = os.path.join(base_path, image_relative_path)
                    downloaded = os.path.exists(image_path)
                    if downloaded:
                        artifact = await self.create_artifact(image_path,
                                                              None,
                                                              None,
                                                              downloaded=downloaded)
                    else:
                        artifact = Artifact()
                    lces = pulp2lazycatalog.filter(pulp2_storage_path=image_path)
                    if lces:
                        for lce in lces:
                            remote = get_remote_by_importer_id(lce.pulp2_importer_id)
                            remotes.add(remote)
                            da = DeclarativeArtifact(
                                artifact=artifact,
                                url=lce.pulp2_url,
                                relative_path=image_relative_path,
                                remote=remote,
                                deferred_download=not downloaded)
                            d_artifacts.append(da)
                            lce.is_migrated = True
                            future_relations['lces'].append(lce)
                    else:
                        da = DeclarativeArtifact(
                            artifact=artifact,
                            url=NOT_USED,
                            relative_path=image_relative_path,
                            remote=None,
                            deferred_download=False)
                        d_artifacts.append(da)

                # We do this last because we need the remote url which is only found in the LCE
                # of the image files. There is no LCE for the .treeninfo file itself.
                relative_path = pulp_2to3_detail_content.relative_path_for_content_artifact
                treeinfo_path = os.path.join(pulp2content.pulp2_storage_path, relative_path)
                artifact = await self.create_artifact(treeinfo_path, None, None, downloaded=True)
                if remotes:
                    for remote in remotes:
                        da = DeclarativeArtifact(
                            artifact=artifact,
                            url=urljoin(remote.url, relative_path),
                            relative_path=relative_path,
                            remote=remote,
                            deferred_download=False,
                        )
                        d_artifacts.append(da)
                else:
                    da = DeclarativeArtifact(
                        artifact=artifact,
                        url=NOT_USED,
                        relative_path=relative_path,
                        remote=None,
                        deferred_download=False,
                    )
                    d_artifacts.append(da)
                dc = DeclarativeContent(content=pulp3content, d_artifacts=d_artifacts)
                dc.extra_data = future_relations
                await self.put(dc)
            # not all content units have files, create DC without artifact
            elif is_artifactless_type:
                # dc without artifact
                dc = DeclarativeContent(content=pulp3content)
                dc.extra_data = future_relations
                await self.put(dc)
            else:

                # create artifact for content that has file
                artifact = await self.create_artifact(pulp2content.pulp2_storage_path,
                                                      pulp_2to3_detail_content.expected_digests,
                                                      pulp_2to3_detail_content.expected_size,
                                                      downloaded=pulp2content.downloaded)

                if is_lazy_type and pulp2lazycatalog:
                    # handle DA and RA creation for content that supports on_demand
                    # Downloaded or on_demand content with LCEs.
                    #
                    # To create multiple remote artifacts, create multiple instances of declarative
                    # content which will differ by url/remote in their declarative artifacts
                    for lce in pulp2lazycatalog:
                        remote = get_remote_by_importer_id(lce.pulp2_importer_id)
                        deferred_download = not pulp2content.downloaded
                        if not remote and deferred_download:
                            _logger.warn(_('On_demand content cannot be migrated without a remote '
                                           'pulp2 unit_id: {}'.format(pulp2content.pulp2_id)))
                            continue

                        relative_path = pulp_2to3_detail_content.relative_path_for_content_artifact
                        da = DeclarativeArtifact(
                            artifact=artifact,
                            url=lce.pulp2_url,
                            relative_path=relative_path,
                            remote=remote,
                            deferred_download=deferred_download)
                        lce.is_migrated = True
                        dc = DeclarativeContent(content=pulp3content, d_artifacts=[da])
                        dc.extra_data = future_relations
                        await self.put(dc)
                    future_relations.update({'lces': list(pulp2lazycatalog)})
                else:
                    da = DeclarativeArtifact(
                        artifact=artifact,
                        url=NOT_USED,
                        relative_path=pulp_2to3_detail_content.relative_path_for_content_artifact,
                        remote=None,
                        deferred_download=False)
                    dc = DeclarativeContent(content=pulp3content, d_artifacts=[da])
                    dc.extra_data = future_relations
                    await self.put(dc)

            if pb:
                pb.increment()

            if has_future and dc:
                futures.append(dc)
            resolve_futures = len(futures) >= batch_size or pb.done == pb.total
            if resolve_futures:
                for dc in futures:
                    await dc.resolution()
                futures.clear()


class UpdateLCEs(Stage):
    """
    Update migrated pulp2lazy_catalog entries with the is_migrated set to True only after
    RemoteArtifact has been saved.
    """
    async def run(self):
        """
        Find LCEs in the extra_data and flip the is_migrated flag to True
        """
        async for batch in self.batches():
            pulp2lces_batch = []
            with transaction.atomic():
                for d_content in batch:
                    lces = d_content.extra_data.get('lces')
                    if lces:
                        pulp2lces_batch.extend(lces)

                Pulp2LazyCatalog.objects.bulk_update(objs=pulp2lces_batch,
                                                     fields=['is_migrated'],
                                                     batch_size=1000)

            for d_content in batch:
                await self.put(d_content)


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
