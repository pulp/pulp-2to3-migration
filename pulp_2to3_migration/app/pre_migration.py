import logging

from collections import namedtuple
from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from mongoengine.queryset.visitor import Q as mongo_Q

from pulpcore.plugin.constants import TASK_STATES
from pulpcore.plugin.models import (
    BaseDistribution,
    Publication,
    ProgressReport,
)
from pulp_2to3_migration.app.constants import DEFAULT_BATCH_SIZE
from pulp_2to3_migration.app.models import (
    Pulp2Content,
    Pulp2Distributor,
    Pulp2Importer,
    Pulp2LazyCatalog,
    Pulp2RepoContent,
    Pulp2Repository,
    RepoSetup,
)
from pulp_2to3_migration.pulp2.base import (
    Distributor,
    Importer,
    LazyCatalogEntry,
    Repository,
    RepositoryContentUnit,
)

_logger = logging.getLogger(__name__)

ContentModel = namedtuple('ContentModel', ['pulp2', 'pulp_2to3_detail'])


def pre_migrate_all_content(plan):
    """
    Pre-migrate all content for the specified plugins.

    Args:
        plan (MigrationPlan): Migration Plan to use for migration.
    """
    _logger.debug('Pre-migrating Pulp 2 content')

    # get all the content models for the migrating plugins
    for plugin in plan.get_plugin_plans():
        for content_type in plugin.migrator.pulp2_content_models:
            # mongodb model
            pulp2_content_model = plugin.migrator.pulp2_content_models[content_type]

            # postgresql model
            pulp_2to3_detail_model = plugin.migrator.content_models[content_type]

            content_model = ContentModel(pulp2=pulp2_content_model,
                                         pulp_2to3_detail=pulp_2to3_detail_model)
            # identify wether the content is mutable
            mutable_type = content_model.pulp2.TYPE_ID in plugin.migrator.mutable_content_models
            # identify wether the content is lazy
            lazy_type = content_model.pulp2.TYPE_ID in plugin.migrator.lazy_types
            # check if the content type has a premigration hook
            premigrate_hook = None
            if content_model.pulp2.TYPE_ID in plugin.migrator.premigrate_hook:
                premigrate_hook = plugin.migrator.premigrate_hook[content_model.pulp2.TYPE_ID]
            pre_migrate_content_type(content_model, mutable_type, lazy_type, premigrate_hook)


def pre_migrate_content_type(content_model, mutable_type, lazy_type, premigrate_hook):
    """
    A coroutine to pre-migrate Pulp 2 content, including all details for on_demand content.

    Args:
        content_model: Models for content which is being migrated.
        mutable_type: Boolean that indicates whether the content type is mutable.
    """
    def delete_removed_pulp2_content(content_model):
        """
        Delete Pulp2Content records for content which is no longer present in Pulp2.

        This is to avoid situations and extra work when not all content migrated during the first
        migration run, then orphan clean up is run in Pulp 2, and then migration is run again.

        Args:
            content_model: Pulp 2 content model

        """
        content_type = content_model.pulp2.TYPE_ID
        mongo_content_qs = content_model.pulp2.objects().only('id')
        mongo_content_ids = {c['_id'] for c in mongo_content_qs.as_pymongo().no_cache()}
        premigrated_content_ids = set(
            Pulp2Content.objects.filter(
                pulp2_content_type_id=content_type
            ).only('pulp2_id').values_list('pulp2_id', flat=True)
        )
        content_ids_to_delete = premigrated_content_ids - mongo_content_ids
        if content_ids_to_delete:
            Pulp2Content.objects.filter(
                pulp2_content_type_id=content_type,
                pulp2_id__in=content_ids_to_delete
            ).delete()

    batch_size = settings.CONTENT_PREMIGRATION_BATCH_SIZE or DEFAULT_BATCH_SIZE
    pulp2content = []
    pulp2mutatedcontent = []
    content_type = content_model.pulp2.TYPE_ID
    set_pulp2_repo = content_model.pulp_2to3_detail.set_pulp2_repo

    delete_removed_pulp2_content(content_model)

    # the latest timestamp we have in the migration tool Pulp2Content table for this content type
    content_qs = Pulp2Content.objects.filter(pulp2_content_type_id=content_type)
    last_updated = content_qs.aggregate(Max('pulp2_last_updated'))['pulp2_last_updated__max'] or 0
    _logger.debug('The latest migrated {type} content has {timestamp} timestamp.'.format(
        type=content_type,
        timestamp=last_updated))

    query_args = {}
    if premigrate_hook:
        pulp2_content_ids = premigrate_hook()
        query_args["id__in"] = pulp2_content_ids

    mongo_content_qs = content_model.pulp2.objects(
        _last_updated__gte=last_updated, **query_args
    ).order_by("_last_updated")

    total_content = mongo_content_qs.count()
    _logger.debug('Total count for {type} content to migrate: {total}'.format(
        type=content_type,
        total=total_content))

    pulp2content_pb = ProgressReport(
        message='Pre-migrating Pulp 2 {} content (general info)'.format(content_type),
        code='premigrating.content.general',
        total=total_content,
        state=TASK_STATES.RUNNING)
    pulp2content_pb.save()
    pulp2detail_pb = ProgressReport(
        message='Pre-migrating Pulp 2 {} content (detail info)'.format(content_type),
        code='premigrating.content.detail',
        total=total_content,
        state=TASK_STATES.RUNNING)
    pulp2detail_pb.save()
    existing_count = 0

    if mutable_type:
        pulp2_content_ids = []

        for c in mongo_content_qs.only('id', '_last_updated').no_cache().as_pymongo():
            if c['_last_updated'] == last_updated:
                if Pulp2Content.objects.filter(
                        pulp2_last_updated=last_updated, pulp2_id=c['_id']).exists():
                    continue

                pulp2_content_ids.append(c['_id'])

        # This is a mutable content type. Query for the existing pulp2content.
        # If any was found, it means that the migrated content is older than the incoming.
        # Delete outdated migrated pulp2content and create a new pulp2content
        outdated = Pulp2Content.objects.filter(pulp2_id__in=pulp2_content_ids)
        if outdated.exists():
            pulp2mutatedcontent.extend(pulp2_content_ids)
        outdated.delete()

    mongo_fields = set(['id', '_storage_path', '_last_updated', '_content_type_id'])
    if hasattr(content_model.pulp2, 'downloaded'):
        mongo_fields.add('downloaded')

    batched_mongo_content_qs = mongo_content_qs.only(*mongo_fields).batch_size(batch_size)
    for i, record in enumerate(batched_mongo_content_qs.no_cache()):
        if record._last_updated == last_updated:
            # corner case - content with the last``last_updated`` date might be pre-migrated;
            # check if this content is already pre-migrated
            migrated = Pulp2Content.objects.filter(pulp2_last_updated=last_updated,
                                                   pulp2_id=record.id)
            if migrated.exists():
                existing_count += 1

                # it has to be updated here and not later, in case all items were migrated before
                # and no new content will be saved.
                pulp2content_pb.total -= 1
                pulp2detail_pb.total -= 1
                continue

        # very old pulp2 content will not have downloaded field set (prior to lazy sync)
        downloaded = hasattr(record, 'downloaded') and (
            record.downloaded or record.downloaded is None
        )

        if set_pulp2_repo:
            # This content requires to set pulp 2 repo. E.g. for errata, because 1 pulp2
            # content unit is converted into N pulp3 content units and repo_id is the only
            # way to have unique records for those.
            content_relations = Pulp2RepoContent.objects.filter(
                pulp2_unit_id=record.id,
                pulp2_content_type_id=record._content_type_id,
                pulp2_repository__not_in_plan=False,
            ).select_related(
                'pulp2_repository'
            ).only(
                'pulp2_repository'
            )
            for relation in content_relations.iterator():
                item = Pulp2Content(
                    pulp2_id=record.id,
                    pulp2_content_type_id=record._content_type_id,
                    pulp2_last_updated=record._last_updated,
                    pulp2_storage_path=record._storage_path,
                    downloaded=downloaded,
                    pulp2_repo=relation.pulp2_repository,
                )
                _logger.debug(
                    'Add content item to the list to migrate: {item}'.format(item=item))
                pulp2content.append(item)
                pulp2content_pb.total += 1
                pulp2detail_pb.total += 1

            # total needs to be adjusted, proper counting happened in the loop above,
            # so we subtract one because this content is also a part of initial 'total' counter.
            pulp2content_pb.total -= 1
            pulp2detail_pb.total -= 1
        else:
            item = Pulp2Content(
                pulp2_id=record.id,
                pulp2_content_type_id=record._content_type_id,
                pulp2_last_updated=record._last_updated,
                pulp2_storage_path=record._storage_path,
                downloaded=downloaded
            )
            _logger.debug('Add content item to the list to migrate: {item}'.format(item=item))
            pulp2content.append(item)

        # determine if the batch needs to be saved, also take into account whether there is
        # anything in the pulp2content to be saved
        save_batch = pulp2content and (len(pulp2content) >= batch_size or i == total_content - 1)
        if save_batch:
            _logger.debug(
                'Bulk save for generic content info, saved so far: {index}'.format(index=i + 1)
            )
            pulp2content_batch = Pulp2Content.objects.bulk_create(pulp2content,
                                                                  ignore_conflicts=True)

            # bulk_create(ignore_conflicts=True) hands back the same item-set we passed in,
            # *even if* it decided to update an existing db-record rather than creating a new
            # one with the passed-in PK. As a result, we can't trust pulp2content_batch to
            # have the 'right' PKs (i.e., the in-memory p2content_batch doesn't match the
            # db-reality). This causes the pre_migrate_content_detail() below to fail as it
            # attempts to create detail-records for the Pulp2Content records it's been handed.
            # THEREFORE - we need to find the 'real' IDs of everything in p2content-batch based
            # on its uniqueness-fields and update the in-memory list with them.
            for p2c in pulp2content_batch:
                filter_q = Q(
                    pulp2_content_type_id=content_type,
                    pulp2_id=p2c.pulp2_id,
                    pulp2_repo=p2c.pulp2_repo,
                    pulp2_subid=p2c.pulp2_subid,
                )
                p2c_db = Pulp2Content.objects.get(filter_q)
                p2c.pulp_id = p2c_db.pulp_id

            content_saved = len(pulp2content_batch) - existing_count
            pulp2content_pb.done += content_saved
            pulp2content_pb.save()

            content_model.pulp_2to3_detail.pre_migrate_content_detail(pulp2content_batch)

            pulp2detail_pb.done += content_saved
            pulp2detail_pb.save()

            pulp2content.clear()
            existing_count = 0

    # If it's a per-repo content type and it's a migration re-run, we need to make sure that the
    # existing content hasn't been associated with a new repo since our last migration,
    # and if so, we need to go back and create a Pulp2Content for these new relations.
    # E.g. errata copied from one repo to another in Pulp 2, in such cases _last_updated is
    # unchanged.
    if set_pulp2_repo and last_updated:
        # last_updated is a unix timestamp, we need to convert it to use in our Django query.
        last_updated = datetime.utcfromtimestamp(last_updated)

        # Query all new relations for that content since the last run
        content_relations = Pulp2RepoContent.objects.filter(
            pulp2_content_type_id=content_type,
            pulp2_repository__not_in_plan=False,
            pulp2_created__gte=last_updated
        ).select_related(
            'pulp2_repository'
        ).only(
            'pulp2_repository', 'pulp2_created',
        ).order_by('pulp2_created')

        mongo_content_qs = content_model.pulp2.objects(
            id__in=content_relations.values_list('pulp2_unit_id', flat=True))
        pulp2_content_by_id = {
            record.id: record for record in mongo_content_qs.only(*mongo_fields).no_cache()
        }

        for relation in content_relations:
            record = pulp2_content_by_id[relation.pulp2_unit_id]
            # very old pulp2 content will not have downloaded field set (prior to lazy sync)
            downloaded = hasattr(record, 'downloaded') and (
                record.downloaded or record.downloaded is None
            )
            specific_content_q = Q(
                pulp2_content_type_id=record._content_type_id,
                pulp2_id=record.id,
                pulp2_repo=relation.pulp2_repository,
                pulp2_subid='',
            )

            # Ensure that no existing pulp2content slipped into bulk_create.
            # Otherwise, we'll have a problem with later bulk_create for detail models.
            if Pulp2Content.objects.filter(specific_content_q).exists():
                continue

            item = Pulp2Content(
                pulp2_id=record.id,
                pulp2_content_type_id=record._content_type_id,
                # Set `pulp2_last_updated` to the date of when a content unit got copied.
                # (We can't set it to anything higher, in case pre-migration crashes and we would
                # need to pick it up correctly on the next re-run.)
                # When erratum is copied in pulp 2, it doesn't change its _last_updated timestamp.
                # It means that Katello has no way to identify that the erratum has been copied
                # since the last migration run, without reimporting all errata, which is expensive.
                pulp2_last_updated=int(relation.pulp2_created.timestamp()),
                pulp2_storage_path=record._storage_path,
                downloaded=downloaded,
                pulp2_repo=relation.pulp2_repository
            )
            _logger.debug(
                'Add content item to the list to migrate: {item}'.format(item=item))
            pulp2content.append(item)
            pulp2content_pb.total += 1
            pulp2detail_pb.total += 1

        pulp2content_batch = Pulp2Content.objects.bulk_create(pulp2content)
        pulp2content_pb.done += len(pulp2content_batch)
        pulp2content_pb.save()

        content_model.pulp_2to3_detail.pre_migrate_content_detail(pulp2content_batch)

        pulp2detail_pb.done += len(pulp2content_batch)
        pulp2detail_pb.save()

    pulp2content_pb.save()
    pulp2detail_pb.save()

    if pulp2mutatedcontent:
        # when we flip the is_migrated flag to False, we base this decision on the last_unit_added
        # https://github.com/pulp/pulp-2to3-migration/blob/master/pulp_2to3_migration/app/pre_migration.py#L279  # noqa
        # in this case, we still need to update the is_migrated flag manually because of errata.
        # in pulp2 sync and copy cases of updated errata are not covered
        # only when uploading errata last_unit_added is updated on all the repos that contain it
        mutated_content = Pulp2RepoContent.objects.filter(pulp2_unit_id__in=pulp2mutatedcontent)
        repo_to_update_ids = mutated_content.values_list(
            'pulp2_repository_id', flat=True).distinct()
        Pulp2Repository.objects.filter(pk__in=repo_to_update_ids).update(is_migrated=False)

    if lazy_type:
        pre_migrate_lazycatalog(content_type)

    pulp2content_pb.state = TASK_STATES.COMPLETED
    pulp2content_pb.save()
    pulp2detail_pb.state = TASK_STATES.COMPLETED
    pulp2detail_pb.save()


def pre_migrate_lazycatalog(content_type):
    """
    A coroutine to pre-migrate Pulp 2 Lazy Catalog Entries (LCE) for a specific content type.

    There is no [quick] way to identify whether the LCE were changed or not in Pulp 2. So every
    time all LCE for the specified type are pre-migrated, nothing is skipped.

    Args:
        content_type: A content type for which LCE should be pre-migrated
    """
    batch_size = 5000
    pulp2lazycatalog = []

    mongo_lce_qs = LazyCatalogEntry.objects(unit_type_id=content_type)
    for lce in mongo_lce_qs.batch_size(batch_size).as_pymongo().no_cache():
        item = Pulp2LazyCatalog(pulp2_importer_id=lce['importer_id'],
                                pulp2_unit_id=lce['unit_id'],
                                pulp2_content_type_id=lce['unit_type_id'],
                                pulp2_storage_path=lce['path'],
                                pulp2_url=lce['url'],
                                pulp2_revision=lce['revision'],
                                is_migrated=False)
        pulp2lazycatalog.append(item)

        if len(pulp2lazycatalog) >= batch_size:
            Pulp2LazyCatalog.objects.bulk_create(pulp2lazycatalog, ignore_conflicts=True)
            pulp2lazycatalog.clear()
    else:
        Pulp2LazyCatalog.objects.bulk_create(pulp2lazycatalog, ignore_conflicts=True)


def pre_migrate_all_without_content(plan):
    """
    Pre-migrate repositories, relations to their contents, importers and distributors.

    Look at the last updated times in the pulp2to3 tables for repositories/importers/distributors:
     * pulp2_last_unit_added or pulp2_last_unit_removed for repositories
     * pulp2_last_updated for importers and distributors

    Query empty-never-had-content repos (can't filter them out in any way) and repos for which
    there were:
     * content changes since the last run
     * importer changes since the last run
     * distributor changes since the last run

    Query in order of last_unit_added for the case when pre-migration is interrupted before we are
    done with repositories.

    Args:
        plan(MigrationPlan): A Migration Plan
    """

    _logger.debug('Pre-migrating Pulp 2 repositories')

    with ProgressReport(message='Processing Pulp 2 repositories, importers, distributors',
                        code='processing.repositories', total=0) as pb:

        for plugin_plan in plan.get_plugin_plans():
            repos = plugin_plan.get_repositories()
            importers_repos = plugin_plan.get_importers_repos()
            distributors_repos = plugin_plan.get_distributors_repos()

            importer_types = list(plugin_plan.migrator.importer_migrators.keys())
            distributor_migrators = plugin_plan.migrator.distributor_migrators
            distributor_types = list(distributor_migrators.keys())

            # figure out which repos/importers/distributors have been updated since the last run
            epoch = datetime.utcfromtimestamp(0)
            repo_type_q = Q(pulp2_repo_type=plugin_plan.type)
            imp_type_q = Q(pulp2_type_id__in=importer_types)
            dist_type_q = Q(pulp2_type_id__in=distributor_types)

            plugin_pulp2repos = Pulp2Repository.objects.filter(repo_type_q)
            repo_premigrated_last_by_added = plugin_pulp2repos.aggregate(
                Max('pulp2_last_unit_added')
            )['pulp2_last_unit_added__max'] or epoch
            repo_premigrated_last_by_removed = plugin_pulp2repos.aggregate(
                Max('pulp2_last_unit_removed')
            )['pulp2_last_unit_removed__max'] or epoch
            imp_premigrated_last = Pulp2Importer.objects.filter(imp_type_q).aggregate(
                Max('pulp2_last_updated')
            )['pulp2_last_updated__max'] or epoch
            dist_premigrated_last = Pulp2Distributor.objects.filter(dist_type_q).aggregate(
                Max('pulp2_last_updated')
            )['pulp2_last_updated__max'] or epoch

            is_content_added_q = mongo_Q(last_unit_added__gte=repo_premigrated_last_by_added)
            is_content_removed_q = mongo_Q(last_unit_removed__gte=repo_premigrated_last_by_removed)
            is_new_enough_repo_q = is_content_added_q | is_content_removed_q
            is_empty_repo_q = mongo_Q(last_unit_added__exists=False)
            is_new_enough_imp_q = mongo_Q(last_updated__gte=imp_premigrated_last)
            is_new_enough_dist_q = mongo_Q(last_updated__gte=dist_premigrated_last)
            repo_repo_id_q = mongo_Q(repo_id__in=repos)
            imp_repo_id_q = mongo_Q(repo_id__in=importers_repos)
            dist_repo_id_q = mongo_Q(repo_id__in=distributors_repos)

            updated_importers = Importer.objects(
                imp_repo_id_q & is_new_enough_imp_q
            ).only('repo_id')
            updated_imp_repos = set(imp.repo_id for imp in updated_importers)
            updated_distributors = Distributor.objects(
                dist_repo_id_q & is_new_enough_dist_q
            ).only('repo_id')
            updated_dist_repos = set(dist.repo_id for dist in updated_distributors)
            updated_impdist_repos = updated_imp_repos | updated_dist_repos

            mongo_updated_repo_q = repo_repo_id_q & (is_new_enough_repo_q | is_empty_repo_q)
            mongo_updated_imp_dist_repo_q = mongo_Q(repo_id__in=updated_impdist_repos)

            mongo_repo_qs = Repository.objects(
                mongo_updated_repo_q | mongo_updated_imp_dist_repo_q
            ).order_by('last_unit_added')

            pb.total += mongo_repo_qs.count()
            pb.save()

            for repo_data in mongo_repo_qs.only('id',
                                                'repo_id',
                                                'last_unit_added',
                                                'last_unit_removed',
                                                'description'):
                repo_id = repo_data.repo_id
                with transaction.atomic():
                    if repo_id in repos:
                        pre_migrate_repo(repo_data, plan.repo_id_to_type)
                    if repo_id in importers_repos:
                        pre_migrate_importer(repo_id, importer_types)
                    if repo_id in distributors_repos:
                        pre_migrate_distributor(repo_id, distributor_migrators)
                    pb.increment()


def pre_migrate_repo(record, repo_id_to_type):
    """
    Pre-migrate a pulp 2 repo.

    NOTE: MongoDB and Django handle datetime fields differently. MongoDB doesn't care about
    timezones and provides "naive" time, while Django is complaining about time without a timezone.
    The problem is that naive time != time with specified timezone, that's why all the time for
    MongoDB comparisons should be naive and all the time for Django/PostgreSQL should be timezone
    aware.

    Args:
        record(Repository): Pulp 2 repository data
        repo_id_to_type(dict): A mapping from a pulp 2 repo_id to pulp 2 repo types

    Return:
        repo(Pulp2Repository): A pre-migrated repository
    """

    last_unit_added = (record.last_unit_added
                       and timezone.make_aware(record.last_unit_added, timezone.utc))
    last_unit_removed = (record.last_unit_removed
                         and timezone.make_aware(record.last_unit_removed, timezone.utc))

    repo, created = Pulp2Repository.objects.get_or_create(
        pulp2_object_id=record.id,
        defaults={'pulp2_repo_id': record.repo_id,
                  'pulp2_last_unit_added': last_unit_added,
                  'pulp2_last_unit_removed': last_unit_removed,
                  'pulp2_description': record.description,
                  'pulp2_repo_type': repo_id_to_type[record.repo_id],
                  'is_migrated': False})

    if not created:
        # if it was marked as such because it was not present in the migration plan
        repo.not_in_plan = False
        # check if there were any changes since last time
        is_changed = (last_unit_added != repo.pulp2_last_unit_added
                      or last_unit_removed != repo.pulp2_last_unit_removed)
        if is_changed:
            repo.pulp2_last_unit_added = last_unit_added
            repo.last_unit_removed = last_unit_removed
            repo.pulp2_description = record.description
            repo.is_migrated = False
        repo.save()

    if created or is_changed:
        pre_migrate_repocontent(repo)

    return repo


def pre_migrate_importer(repo_id, importer_types):
    """
    Pre-migrate a pulp 2 importer.

    Args:
        repo_id(str): An id of a pulp 2 repository which importer should be migrated
        importer_types(list): a list of supported importer types
    """
    mongo_importer_q = mongo_Q(repo_id=repo_id, importer_type_id__in=importer_types)

    # importers with empty config are not needed - nothing to migrate
    mongo_importer_q &= mongo_Q(config__exists=True) & mongo_Q(config__ne={})

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
        msg = 'Importer from {repo} cannot be migrated because it does not have a feed'.format(
            repo=repo_id)
        _logger.warn(msg)
        return

    last_updated = (importer_data.last_updated
                    and timezone.make_aware(importer_data.last_updated, timezone.utc))

    importer, created = Pulp2Importer.objects.get_or_create(
        pulp2_object_id=importer_data.id,
        defaults={'pulp2_type_id': importer_data.importer_type_id,
                  'pulp2_last_updated': last_updated,
                  'pulp2_config': importer_data.config,
                  'pulp2_repo_id': repo_id,
                  'is_migrated': False})

    if not created:
        # if it was marked as such because it was not present in the migration plan
        importer.not_in_plan = False
        # check if there were any changes since last time
        if last_updated != importer.pulp2_last_updated:
            # remove Remote in case of feed change
            if importer.pulp2_config.get('feed') != importer_data.config.get('feed'):
                importer.pulp3_remote.delete()
                importer.pulp3_remote = None
                # do not flip is_migrated to False for LCE for at least once migrated importer

            importer.pulp2_last_updated = last_updated
            importer.pulp2_config = importer_data.config
            importer.is_migrated = False
        importer.save()


def pre_migrate_distributor(repo_id, distributor_migrators):
    """
    Pre-migrate a pulp 2 distributor.

    Args:
        repo_id(str): An id of a pulp 2 repository which distributor should be migrated
        distributor_migrators(dict): supported distributor types and their models for migration
    """
    distributor_types = list(distributor_migrators.keys())
    mongo_distributor_q = mongo_Q(repo_id=repo_id,
                                  distributor_type_id__in=distributor_types)

    mongo_distributor_qs = Distributor.objects(mongo_distributor_q)
    if not mongo_distributor_qs:
        # Either the distributor no longer exists in Pulp2,
        # or it was filtered out by the Migration Plan,
        # or it has an empty config
        return

    for dist_data in mongo_distributor_qs:
        last_updated = (dist_data.last_updated
                        and timezone.make_aware(dist_data.last_updated, timezone.utc))

        distributor, created = Pulp2Distributor.objects.get_or_create(
            pulp2_object_id=dist_data.id,
            defaults={'pulp2_id': dist_data.distributor_id,
                      'pulp2_type_id': dist_data.distributor_type_id,
                      'pulp2_last_updated': last_updated,
                      'pulp2_config': dist_data.config,
                      'pulp2_repo_id': repo_id,
                      'is_migrated': False})

        if not created:
            # if it was marked as such because it was not present in the migration plan
            distributor.not_in_plan = False

            if last_updated != distributor.pulp2_last_updated:
                distributor.pulp2_config = dist_data.config
                distributor.pulp2_last_updated = last_updated
                distributor.is_migrated = False
                dist_migrator = distributor_migrators.get(distributor.pulp2_type_id)
                needs_new_publication = dist_migrator.needs_new_publication(distributor)
                needs_new_distribution = dist_migrator.needs_new_distribution(distributor)
                remove_publication = needs_new_publication and distributor.pulp3_publication
                remove_distribution = needs_new_distribution and distributor.pulp3_distribution

                if remove_publication:
                    # check if publication is shared by multiple distributions
                    # on the corresponding distributor flip the flag to false so the affected
                    # distribution will be updated with the new publication
                    pulp2dists = distributor.pulp3_publication.pulp2distributor_set.all()
                    for dist in pulp2dists:
                        if dist.is_migrated:
                            dist.is_migrated = False
                            dist.save()
                    distributor.pulp3_publication.delete()
                    distributor.pulp3_publication = None
                if remove_publication or remove_distribution:
                    distributor.pulp3_distribution.delete()
                    distributor.pulp3_distribution = None

            distributor.save()


def pre_migrate_repocontent(repo):
    """
    Pre-migrate a relation between repositories and content in pulp 2.

    Args:
        repo(Pulp2Repository): A pre-migrated pulp 2 repository which importer should be migrated
    """
    if repo.is_migrated:
        return

    # At this stage the pre-migrated repo is either new or changed since the last run.
    # For the case when something changed, old repo-content relations should be removed.
    Pulp2RepoContent.objects.filter(pulp2_repository=repo).delete()

    mongo_repocontent_q = mongo_Q(repo_id=repo.pulp2_repo_id)
    mongo_repocontent_qs = RepositoryContentUnit.objects(mongo_repocontent_q)

    repocontent = []
    for repocontent_data in mongo_repocontent_qs.exclude('repo_id').as_pymongo().no_cache():
        item = Pulp2RepoContent(
            pulp2_unit_id=repocontent_data['unit_id'],
            pulp2_content_type_id=repocontent_data['unit_type_id'],
            pulp2_repository=repo,
            pulp2_created=repocontent_data['created'],
            pulp2_updated=repocontent_data['updated']
        )
        repocontent.append(item)

    if not repocontent:
        # Either the repo no longer exists in Pulp 2, or the repo is empty.
        return

    Pulp2RepoContent.objects.bulk_create(repocontent, batch_size=DEFAULT_BATCH_SIZE)


def handle_outdated_resources(plan):
    """
    Marks repositories, importers, distributors which are no longer present in Pulp2.

    Delete Publications and Distributions which are no longer present in Pulp2.

    Args:
        plan(MigrationPlan): A Migration Plan
    """
    plugins = plan.get_plugins()
    RepoSetup.mark_changed_relations(plugins)
    RepoSetup.finalize(plugins)

    for plugin_plan in plan.get_plugin_plans():
        inplan_repos = plugin_plan.get_repositories()

        # filter by repo type and by the repos specified in a plan
        repos_to_consider = plan.type_to_repo_ids[plugin_plan.type]
        repos_to_consider = set(inplan_repos).intersection(repos_to_consider)

        mongo_repo_q = mongo_Q(repo_id__in=repos_to_consider)
        mongo_repo_obj_ids = set(str(i.id) for i in Repository.objects(mongo_repo_q).only('id'))

        repo_type_q = Q(pulp2_repo_type=plugin_plan.type)
        inplan_repo_q = Q(pulp2_object_id__in=mongo_repo_obj_ids)
        Pulp2Repository.objects.filter(repo_type_q).exclude(inplan_repo_q).update(not_in_plan=True)

        # Mark removed or excluded importers
        inplan_imp_repos = plugin_plan.get_importers_repos()
        mongo_imp_q = mongo_Q(repo_id__in=inplan_imp_repos)
        mongo_imp_obj_ids = set(str(i.id) for i in Importer.objects(mongo_imp_q).only('id'))
        imp_types = plugin_plan.migrator.importer_migrators.keys()

        imp_type_q = Q(pulp2_type_id__in=imp_types)
        inplan_imp_q = Q(pulp2_object_id__in=mongo_imp_obj_ids)
        Pulp2Importer.objects.filter(imp_type_q).exclude(inplan_imp_q).update(not_in_plan=True)

        # Mark removed or excluded distributors
        inplan_dist_repos = plugin_plan.get_distributors_repos()
        mongo_dist_q = mongo_Q(repo_id__in=inplan_dist_repos)
        mongo_dist_obj_ids = set(str(i.id) for i in Distributor.objects(mongo_dist_q).only('id'))
        dist_types = plugin_plan.migrator.distributor_migrators.keys()

        dist_type_q = Q(pulp2_type_id__in=dist_types)
        inplan_dist_q = Q(pulp2_object_id__in=mongo_dist_obj_ids)
        Pulp2Distributor.objects.filter(dist_type_q).exclude(inplan_dist_q).update(not_in_plan=True)

    # Delete old Publications/Distributions which are no longer present in Pulp2.

    # It's critical to remove Distributions to avoid base_path overlap.
    # It makes the migration logic easier if we remove old Publications as well.

    # Delete criteria:
    #     - pulp2distributor is no longer in plan
    #     - pulp2repository content changed (repo.is_migrated=False) or it is no longer in plan

    repos_with_old_distributions_qs = Pulp2Repository.objects.filter(
        Q(is_migrated=False) | Q(not_in_plan=True)
    )

    old_dist_query = Q(pulp3_distribution__isnull=False) | Q(pulp3_publication__isnull=False)
    old_dist_query &= Q(pulp2_repos__in=repos_with_old_distributions_qs) | Q(not_in_plan=True)

    with transaction.atomic():
        pulp2distributors_with_old_distributions_qs = Pulp2Distributor.objects.filter(
            old_dist_query
        )

        pulp2distributors_with_old_distributions_qs.update(
            is_migrated=False
        )

        # If publication is shared by multiple distributions, on the corresponding distributors
        # flip the flag to false so the affected distributions will be updated with the new
        # publication
        Pulp2Distributor.objects.filter(
            pulp3_publication__in=Publication.objects.filter(
                pulp2distributor__in=pulp2distributors_with_old_distributions_qs
            )
        ).update(is_migrated=False)

        # Delete outdated publications
        Publication.objects.filter(
            pulp2distributor__in=pulp2distributors_with_old_distributions_qs).delete()

        # Delete outdated distributions
        BaseDistribution.objects.filter(
            pulp2distributor__in=pulp2distributors_with_old_distributions_qs).delete()

        # Remove relations to the pulp2repository in case the relation changed.
        # Pulp2Distributors with is_migrated=false is handled and re-added properly at
        # migration stage.
        # NOTE: this needs to be removed last, the queries above use this relation.
        not_migrated_dists = Pulp2Distributor.objects.filter(is_migrated=False).only('pulp_id')
        Pulp2Distributor.pulp2_repos.through.objects.filter(
            pulp2distributor__in=not_migrated_dists
        ).delete()
