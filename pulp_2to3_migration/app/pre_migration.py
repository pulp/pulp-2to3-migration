import asyncio
import logging

from collections import namedtuple
from datetime import datetime

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from mongoengine.queryset.visitor import Q as mongo_Q

from pulpcore.constants import TASK_STATES
from pulpcore.plugin.models import ProgressReport

from pulp_2to3_migration.app.models import (
    Pulp2Content,
    Pulp2Distributor,
    Pulp2Importer,
    Pulp2LazyCatalog,
    Pulp2RepoContent,
    Pulp2Repository,
)
from pulp_2to3_migration.app.plugin import PLUGIN_MIGRATORS
from pulp_2to3_migration.pulp2.base import (
    Distributor,
    Importer,
    LazyCatalogEntry,
    Repository,
    RepositoryContentUnit,
)

_logger = logging.getLogger(__name__)

ContentModel = namedtuple('ContentModel', ['pulp2', 'pulp_2to3_detail'])


async def pre_migrate_all_content(plan):
    """
    Pre-migrate all content for the specified plugins.

    Args:
        plan (MigrationPlan): Migration Plan to use for migration.
    """
    plugins_to_migrate = plan.get_plugins()
    pre_migrators = []

    # get all the content models for the migrating plugins
    for plugin, plugin_migrator in PLUGIN_MIGRATORS.items():
        if plugin not in plugins_to_migrate:
            continue
        for content_type in plugin_migrator.pulp2_content_models:
            # mongodb model
            pulp2_content_model = plugin_migrator.pulp2_content_models[content_type]

            # postgresql model
            pulp_2to3_detail_model = plugin_migrator.content_models[content_type]

            content_model = ContentModel(pulp2=pulp2_content_model,
                                         pulp_2to3_detail=pulp_2to3_detail_model)
            pre_migrators.append(pre_migrate_content(content_model))

    _logger.debug('Pre-migrating Pulp 2 content')
    await asyncio.wait(pre_migrators)


async def pre_migrate_content(content_model):
    """
    A coroutine to pre-migrate Pulp 2 content, including all details for on_demand content.

    Args:
        content_model: Models for content which is being migrated.
    """
    batch_size = 10000
    content_type = content_model.pulp2.type
    pulp2content = []

    # the latest timestamp we have in the migration tool Pulp2Content table for this content type
    content_qs = Pulp2Content.objects.filter(pulp2_content_type_id=content_type)
    last_updated = content_qs.aggregate(Max('pulp2_last_updated'))['pulp2_last_updated__max'] or 0
    _logger.debug('The latest migrated {type} content has {timestamp} timestamp.'.format(
        type=content_type,
        timestamp=last_updated))

    # query only newly created/updated items
    mongo_content_qs = content_model.pulp2.objects(_last_updated__gte=last_updated)
    total_content = mongo_content_qs.count()
    _logger.debug('Total count for {type} content to migrate: {total}'.format(
        type=content_type,
        total=total_content))

    pulp2content_pb = ProgressReport(
        message='Pre-migrating Pulp 2 {} content (general info)'.format(content_type.upper()),
        code='premigrating.content.general',
        total=total_content,
        state=TASK_STATES.RUNNING)
    pulp2content_pb.save()
    pulp2detail_pb = ProgressReport(
        message='Pre-migrating Pulp 2 {} content (detail info)'.format(content_type.upper()),
        code='premigrating.content.detail',
        total=total_content,
        state=TASK_STATES.RUNNING)
    pulp2detail_pb.save()
    existing_count = 0
    fields = set(['id', '_storage_path', '_last_updated', '_content_type_id'])
    if hasattr(content_model.pulp2, 'downloaded'):
        fields.add('downloaded')
    for i, record in enumerate(mongo_content_qs.only(*fields).batch_size(batch_size)):
        if record._last_updated == last_updated:
            # corner case - content with the last``last_updated`` date might be pre-migrated;
            # check if this content is already pre-migrated
            migrated = Pulp2Content.objects.filter(pulp2_last_updated=last_updated,
                                                   pulp2_id=record.id)
            if migrated:
                existing_count += 1

                # it has to be updated here and not later, in case all items were migrated before
                # and no new content will be saved.
                pulp2content_pb.total -= 1
                pulp2content_pb.save()
                pulp2detail_pb.total -= 1
                pulp2detail_pb.save()
                continue

        downloaded = record.downloaded if hasattr(record, 'downloaded') else False
        item = Pulp2Content(pulp2_id=record.id,
                            pulp2_content_type_id=record._content_type_id,
                            pulp2_last_updated=record._last_updated,
                            pulp2_storage_path=record._storage_path,
                            downloaded=downloaded)
        _logger.debug('Add content item to the list to migrate: {item}'.format(item=item))
        pulp2content.append(item)

        save_batch = (i and not (i + 1) % batch_size or i == total_content - 1)
        if save_batch:
            _logger.debug('Bulk save for generic content info, saved so far: {index}'.format(
                index=i + 1))
            pulp2content_batch = Pulp2Content.objects.bulk_create(pulp2content,
                                                                  ignore_conflicts=True)
            content_saved = len(pulp2content_batch) - existing_count
            pulp2content_pb.done += content_saved
            pulp2content_pb.save()

            await content_model.pulp_2to3_detail.pre_migrate_content_detail(pulp2content_batch)

            pulp2detail_pb.done += content_saved
            pulp2detail_pb.save()

            pulp2content = []
            existing_count = 0

    await pre_migrate_lazycatalog(content_type)

    pulp2content_pb.state = TASK_STATES.COMPLETED
    pulp2content_pb.save()
    pulp2detail_pb.state = TASK_STATES.COMPLETED
    pulp2detail_pb.save()


async def pre_migrate_lazycatalog(content_type):
    """
    A coroutine to pre-migrate Pulp 2 Lazy Catalog Entries (LCE) for a specific content type.

    There is no [quick] way to identify whether the LCE were changed or not in Pulp 2. So every
    time all LCE for the specified type are pre-migrated, nothing is skipped.

    Args:
        content_type: A content type for which LCE should be pre-migrated
    """
    batch_size = 10000
    pulp2lazycatalog = []

    # delete previous pre-migration results since it might be outdated
    Pulp2LazyCatalog.objects.filter(pulp2_content_type_id=content_type).delete()

    mongo_lce_qs = LazyCatalogEntry.objects(unit_type_id=content_type)
    total_lce = mongo_lce_qs.count()
    for i, lce in enumerate(mongo_lce_qs.batch_size(batch_size)):
        item = Pulp2LazyCatalog(pulp2_importer_id=lce.importer_id,
                                pulp2_unit_id=lce.unit_id,
                                pulp2_content_type_id=lce.unit_type_id,
                                pulp2_storage_path=lce.path,
                                pulp2_url=lce.url,
                                pulp2_revision=lce.revision)
        pulp2lazycatalog.append(item)

        save_batch = (i and not (i + 1) % batch_size or i == total_lce - 1)
        if save_batch:
            Pulp2LazyCatalog.objects.bulk_create(pulp2lazycatalog, ignore_conflicts=True)
            pulp2lazycatalog = []


async def pre_migrate_all_without_content(plan):
    """
    Pre-migrate repositories, relations to their contents, importers and distributors.

    NOTE: MongoDB and Django handle datetime fields differently. MongoDB doesn't care about
    timezones and provides "naive" time, while Django is complaining about time without a timezone.
    The problem is that naive time != time with specified timezone, that's why all the time for
    MongoDB comparisons should be naive and all the time for Django/PostgreSQL should be timezone
    aware.

    Args:
        plan(MigrationPlan): A Migration Plan
    """
    repos = plan.get_repositories()
    importers = plan.get_importers()
    distributors = plan.get_distributors()

    _logger.debug('Pre-migrating Pulp 2 repositories')

    # the latest time we have in the migration tool in Pulp2Repository table
    zero_datetime = timezone.make_aware(datetime(1970, 1, 1), timezone.utc)
    last_added = Pulp2Repository.objects.aggregate(Max('pulp2_last_unit_added'))[
        'pulp2_last_unit_added__max'] or zero_datetime
    last_removed = Pulp2Repository.objects.aggregate(Max('pulp2_last_unit_removed'))[
        'pulp2_last_unit_removed__max'] or zero_datetime
    last_updated = max(last_added, last_removed)
    last_updated_naive = timezone.make_naive(last_updated, timezone=timezone.utc)

    with ProgressReport(message='Pre-migrating Pulp 2 repositories, importers, distributors',
                        code='premigrating.repositories') as pb:
        # we pre-migrate:
        #  - empty repos (last_unit_added is not set)
        #  - repos which were updated since last migration (last_unit_added/removed >= last_updated)
        mongo_repo_q = (mongo_Q(last_unit_added__exists=False)
                        | mongo_Q(last_unit_added__gte=last_updated_naive)
                        | mongo_Q(last_unit_removed__gte=last_updated_naive))

        # in case only certain repositories are specified in the migration plan
        if repos:
            mongo_repo_q &= mongo_Q(repo_id__in=repos)

        # filter repo type
        repo_types = [f'{type}-repo' for type in plan.get_plugins()]
        mongo_repo_q &= mongo_Q(__raw__={"notes._repo-type": {'$in': repo_types}})

        mongo_repo_qs = Repository.objects(mongo_repo_q)
        pb.total = mongo_repo_qs.count()
        pb.save()

        distributor_types = []
        importer_types = []
        plugins_to_migrate = plan.get_plugins()

        for plugin, plugin_migrator in PLUGIN_MIGRATORS.items():
            if plugin not in plugins_to_migrate:
                continue
            distributor_types.extend(plugin_migrator.distributor_migrators.keys())
            importer_types.extend(plugin_migrator.importer_migrators.keys())

        for repo_data in mongo_repo_qs.only('id',
                                            'repo_id',
                                            'last_unit_added',
                                            'last_unit_removed',
                                            'description',
                                            'notes'):

            with transaction.atomic():
                repo = await pre_migrate_repo(repo_data)
                await pre_migrate_importer(repo, importers, importer_types)
                await pre_migrate_distributor(repo, distributors, distributor_types)
                await pre_migrate_repocontent(repo)
            pb.increment()


async def pre_migrate_repo(record):
    """
    Pre-migrate a pulp 2 repo.

    Args:
        record(Repository): Pulp 2 repository data

    Return:
        repo(Pulp2Repository): A pre-migrated repository
    """

    last_unit_added = (record.last_unit_added
                       and timezone.make_aware(record.last_unit_added, timezone.utc))
    last_unit_removed = (record.last_unit_removed
                         and timezone.make_aware(record.last_unit_removed, timezone.utc))

    # repo is mutable, it needs to be created or updated
    repo, created = Pulp2Repository.objects.update_or_create(
        pulp2_object_id=record.id,
        defaults={'pulp2_repo_id': record.repo_id,
                  'pulp2_last_unit_added': last_unit_added,
                  'pulp2_last_unit_removed': last_unit_removed,
                  'pulp2_description': record.description,
                  'is_migrated': False,
                  'type': record.notes.get('_repo-type')[:-5]})

    return repo


async def pre_migrate_importer(repo, importers, importer_types):
    """
    Pre-migrate a pulp 2 importer.

    Args:
        repo(Pulp2Repository): A pre-migrated pulp 2 repository which importer should be migrated
        importers(list): A list of importers which are expected to be migrated. If empty,
                         all are migrated.
    """
    mongo_importer_q = mongo_Q(repo_id=repo.pulp2_repo_id, importer_type_id__in=importer_types)

    # importers with empty config are not needed - nothing to migrate
    mongo_importer_q &= mongo_Q(config__exists=True) & mongo_Q(config__ne={})

    # in case only certain importers are specified in the migration plan
    if importers:
        mongo_importer_q &= mongo_Q(repo_id__in=importers)

    mongo_importer_qs = Importer.objects(mongo_importer_q)
    if not mongo_importer_qs:
        # Either the importer no longer exists in Pulp2,
        # or it was filtered out by the Migration Plan,
        # or it has an empty config
        return

    importer_data = mongo_importer_qs.only('id',
                                           'repo_id',
                                           'importer_type_id',
                                           'last_updated',
                                           'config').first()

    if not importer_data.config.get('feed'):
        # Pulp 3 remotes require URL
        return

    last_updated = (importer_data.last_updated
                    and timezone.make_aware(importer_data.last_updated, timezone.utc))

    # importer is mutable, it needs to be created or updated
    Pulp2Importer.objects.update_or_create(
        pulp2_object_id=importer_data.id,
        defaults={'pulp2_type_id': importer_data.importer_type_id,
                  'pulp2_last_updated': last_updated,
                  'pulp2_config': importer_data.config,
                  'pulp2_repository': repo,
                  'is_migrated': False})


async def pre_migrate_distributor(repo, distributors, distributor_types):
    """
    Pre-migrate a pulp 2 distributor.

    Args:
        repo(Pulp2Repository): A pre-migrated pulp 2 repository which distributor should be migrated
        distributors(list): A list of distributors which are expected to be migrated. If empty,
                            all are migrated.
    """
    mongo_distributor_q = mongo_Q(repo_id=repo.pulp2_repo_id,
                                  distributor_type_id__in=distributor_types)

    # in case only certain distributors are specified in the migration plan
    if distributors:
        mongo_distributor_q &= mongo_Q(repo_id__in=distributors)

    mongo_distributor_qs = Distributor.objects(mongo_distributor_q)
    if not mongo_distributor_qs:
        # Either the distributor no longer exists in Pulp2,
        # or it was filtered out by the Migration Plan,
        # or it has an empty config
        return

    for dist_data in mongo_distributor_qs:
        last_updated = (dist_data.last_updated
                        and timezone.make_aware(dist_data.last_updated, timezone.utc))

        # distributor is mutable, it needs to be created or updated
        Pulp2Distributor.objects.update_or_create(
            pulp2_object_id=dist_data.id,
            defaults={'pulp2_id': dist_data.distributor_id,
                      'pulp2_type_id': dist_data.distributor_type_id,
                      'pulp2_last_updated': last_updated,
                      'pulp2_config': dist_data.config,
                      'pulp2_auto_publish': dist_data.auto_publish,
                      'pulp2_repository': repo,
                      'is_migrated': False})


async def pre_migrate_repocontent(repo):
    """
    Pre-migrate a relation between repositories and content in pulp 2.

    Args:
        repo(Pulp2Repository): A pre-migrated pulp 2 repository which importer should be migrated
    """
    # At this stage the pre-migrated repo is either new or changed since the last run.
    # For the case when something changed, old repo-content relations should be removed.
    Pulp2RepoContent.objects.filter(pulp2_repository=repo).delete()

    mongo_repocontent_q = mongo_Q(repo_id=repo.pulp2_repo_id)
    mongo_repocontent_qs = RepositoryContentUnit.objects(mongo_repocontent_q)
    if not mongo_repocontent_qs:
        # Either the repo no longer exists in Pulp 2,
        # or the repo is empty.
        return

    repocontent = []
    for repocontent_data in mongo_repocontent_qs.only('unit_id',
                                                      'unit_type_id'):
        item = Pulp2RepoContent(pulp2_unit_id=repocontent_data.unit_id,
                                pulp2_content_type_id=repocontent_data.unit_type_id,
                                pulp2_repository=repo)
        repocontent.append(item)

    Pulp2RepoContent.objects.bulk_create(repocontent)
