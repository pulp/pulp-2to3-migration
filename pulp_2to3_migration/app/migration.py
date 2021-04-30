import logging

from django.db.models import F, Q
from gettext import gettext as _

from pygtrie import StringTrie

from pulpcore.plugin.models import (
    Content,
    ContentArtifact,
    CreatedResource,
    ProgressReport,
    Repository,
    TaskGroup,
)

from pulpcore.plugin.tasking import enqueue_with_reservation

from pulp_2to3_migration.app.models import (
    Pulp2Content,
    Pulp2Importer,
    Pulp2Distributor,
    Pulp2RepoContent,
    Pulp2Repository,
)

_logger = logging.getLogger(__name__)


def migrate_content(plan, skip_corrupted=False):
    """
    A coroutine to initiate content migration for each plugin.

    Args:
         plan (MigrationPlan): Migration Plan to use
         skip_corrupted (bool): If True, corrupted content is skipped during migration,
                                no task failure.

    """
    progress_data = dict(message='Migrating content to Pulp 3', code='migrating.content', total=0)
    with ProgressReport(**progress_data) as pb:
        # schedule content migration into Pulp 3 using pre-migrated Pulp 2 content
        for plugin in plan.get_plugin_plans():
            # only used for progress bar counters
            content_types = plugin.migrator.content_models.keys()
            num_to_migrate = Pulp2Content.objects.filter(
                pulp2_content_type_id__in=content_types,
                pulp3_content=None
            ).count()

            pb.total += num_to_migrate
            pb.save()

            # migrate
            plugin.migrator.migrate_content_to_pulp3(skip_corrupted=skip_corrupted)

            pb.done = pb.total
            pb.save()


def migrate_repositories(plan):
    """
    A coroutine to migrate pre-migrated repositories.
    """

    progress_data = dict(
        message='Creating repositories in Pulp 3', code='creating.repositories', total=0
    )
    with ProgressReport(**progress_data) as pb:
        for plugin in plan.get_plugin_plans():
            # all pulp2 repos in current plan were already migrated, no need to proceed
            not_migrated_repos = Pulp2Repository.objects.filter(
                is_migrated=False,
                not_in_plan=False,
                pulp2_repo_type=plugin.type
            )
            if not not_migrated_repos.exists():
                continue

            pulp2repos_qs = Pulp2Repository.objects.filter(
                pulp3_repository_version=None,
                not_in_plan=False,
                pulp2_repo_type=plugin.type,
            )
            repos_to_create = plugin.get_repo_creation_setup()
            pb.total += len(repos_to_create)
            pb.save()

            for pulp3_repo_name in repos_to_create:
                try:
                    pulp2repo = pulp2repos_qs.get(pulp2_repo_id=pulp3_repo_name)
                except Pulp2Repository.DoesNotExist:
                    description = pulp3_repo_name
                else:
                    description = pulp2repo.pulp2_description
                repository_class = plugin.migrator.pulp3_repository
                repo, created = repository_class.objects.get_or_create(
                    name=pulp3_repo_name,
                    defaults={'description': description})

                pulp2_repo_ids = []
                repo_version_setup = repos_to_create[pulp3_repo_name].get('repository_versions')
                for repo_version in repo_version_setup:
                    pulp2_repo_ids.append(repo_version['repo_id'])
                pulp2repos_qs = Pulp2Repository.objects.filter(
                    pulp2_repo_id__in=pulp2_repo_ids, pulp3_repository__isnull=True
                )
                pulp2repos_qs.update(pulp3_repository=repo)

                if created:
                    pb.increment()
                else:
                    pb.total -= 1
                    pb.save()


def migrate_importers(plan):
    """
    A coroutine to migrate pre-migrated importers.

    Args:
        plan (MigrationPlan): Migration Plan to use.
    """
    # gather all needed plugin importer migrators
    importer_migrators = {}

    for plugin in plan.get_plugin_plans():
        importer_migrators.update(**plugin.migrator.importer_migrators)

    progress_data = dict(
        message='Migrating importers to Pulp 3', code='migrating.importers', total=0
    )
    with ProgressReport(**progress_data) as pb:
        pulp2importers_qs = Pulp2Importer.objects.filter(
            is_migrated=False, not_in_plan=False)
        pb.total += pulp2importers_qs.count()
        pb.save()

        for pulp2importer in pulp2importers_qs:
            importer_migrator = importer_migrators.get(pulp2importer.pulp2_type_id)
            remote, created = importer_migrator.migrate_to_pulp3(pulp2importer)
            pulp2importer.pulp3_remote = remote
            pulp2importer.is_migrated = True
            pulp2importer.save()
            if created:
                pb.increment()
            else:
                pb.total -= 1
                pb.save()


def complex_repo_migration(plugin, pulp3_repo_setup, repo_name):
    """Perform a complex migration for a particular repo using the repo setup config.

    Create all repository versions, publications, distributions.

    Args:
        plugin: Plugin object
        pulp3_repo_setup: Pulp 3 repo setup config for a plugin
        repo_name: Name of the repo to be migrated
    """
    distributor_migrators = plugin.migrator.distributor_migrators
    distributor_types = list(plugin.migrator.distributor_migrators.keys())
    repo_versions_setup = pulp3_repo_setup[repo_name]['repository_versions']

    # importer might not be migrated, e.g. config is empty or it's not specified in a MP
    pulp3_remote = None
    pulp2_importer_repo_id = pulp3_repo_setup[repo_name].get('pulp2_importer_repository_id')
    if pulp2_importer_repo_id:
        try:
            pulp2_importer = Pulp2Importer.objects.get(
                pulp2_repo_id=pulp2_importer_repo_id,
                not_in_plan=False
            )
            pulp3_remote = pulp2_importer.pulp3_remote
        except Pulp2Importer.DoesNotExist:
            pass

    task_group = TaskGroup.current()
    # find appropriate group_progress_reports that later will be updated
    progress_dist = task_group.group_progress_reports.filter(
        code='create.distribution'
    )
    progress_rv = task_group.group_progress_reports.filter(
        code='create.repo_version'
    )

    for pulp2_repo_info in repo_versions_setup:
        try:
            pulp2_repo = Pulp2Repository.objects.get(
                pulp2_repo_id=pulp2_repo_info['repo_id'],
                not_in_plan=False
            )
        except Pulp2Repository.DoesNotExist:
            # not in Pulp 2 anymore
            continue
        else:
            # it's possible to have a random order of the repo versions (after migration
            # re-run, a repo can be changed in pulp 2 and it might not be for the last
            # repo version)
            create_repo_version(progress_rv, pulp2_repo, pulp3_remote)

    for pulp2_repo_info in repo_versions_setup:
        # find pulp2repo by id
        repo_id = pulp2_repo_info['repo_id']
        dist_repositories = pulp2_repo_info['dist_repo_ids']

        try:
            migrated_repo = Pulp2Repository.objects.get(pulp2_repo_id=repo_id,
                                                        not_in_plan=False,
                                                        is_migrated=True)
        except Pulp2Repository.DoesNotExist:
            # not in Pulp 2 anymore
            continue
        else:
            pulp2dist = Pulp2Distributor.objects.filter(
                is_migrated=False,
                not_in_plan=False,
                pulp2_repo_id__in=dist_repositories,
                pulp2_type_id__in=distributor_types,
            )
            # decrease the number of total because some dists have already been migrated
            decrease_total = len(dist_repositories) - len(pulp2dist)
            if decrease_total:
                progress_dist.update(total=F('total') - decrease_total)

            for dist in pulp2dist:
                dist_migrator = distributor_migrators.get(dist.pulp2_type_id)
                migrate_repo_distributor(
                    dist_migrator, progress_dist, dist,
                    migrated_repo.pulp3_repository_version
                )
                # add distirbutors specified in the complex plan
                # these can be native and not native distributors
                migrated_repo.pulp2_dists.add(dist)


def create_repoversions_publications_distributions(plan, parallel=True):
    """
    A coroutine to create repository versions.

    Content to a repo version is added based on pre-migrated RepoContentUnit and info provided
    in the migration plan.

    Args:
        plan (MigrationPlan): Migration Plan to use.

    Kwargs:
        parallel (bool): If True, attempt to migrate things in parallel where possible.
    """
    for plugin in plan.get_plugin_plans():
        # verify whether all pulp2 repos and distributors have been migrated
        not_migrated_repos = Pulp2Repository.objects.filter(
            is_migrated=False,
            not_in_plan=False,
            pulp2_repo_type=plugin.type)
        not_migrated_dists = Pulp2Distributor.objects.filter(
            is_migrated=False,
            not_in_plan=False,
            pulp2_type_id__in=plugin.migrator.distributor_migrators.keys())
        # no need to proceed - everything is migrated
        if not not_migrated_repos and not not_migrated_dists:
            continue
        not_migrated_repo_ids = not_migrated_repos.values_list('pulp2_repo_id', flat=True)
        not_migrated_repo_ids_dists = not_migrated_dists.values_list('pulp2_repo_id', flat=True)
        repos_ids_to_check = set(not_migrated_repo_ids).union(not_migrated_repo_ids_dists)

        pulp3_repo_setup = plugin.get_repo_creation_setup()

        repo_ver_to_create = 0
        dist_to_create = 0

        if parallel:
            for repo_name in pulp3_repo_setup:
                repo_versions = pulp3_repo_setup[repo_name]['repository_versions']
                needs_a_task = False
                for repo_ver in repo_versions:
                    repos = set(repo_ver['dist_repo_ids'] + [repo_ver['repo_id']])
                    # check whether any resources are not migrated and need a task
                    if repos.intersection(repos_ids_to_check):
                        needs_a_task = True
                        dist_to_create += len(repo_ver['dist_repo_ids'])
                if needs_a_task:
                    repo_ver_to_create += len(repo_versions)
                    repo = Repository.objects.get(name=repo_name).cast()
                    task_args = [plugin, pulp3_repo_setup, repo_name]
                    enqueue_with_reservation(
                        complex_repo_migration,
                        [repo],
                        args=task_args,
                        task_group=TaskGroup.current()
                    )
        else:
            # Serial (non-parallel)
            for repo_name in pulp3_repo_setup:
                repo_versions = pulp3_repo_setup[repo_name]['repository_versions']
                needs_a_task = False
                for repo_ver in repo_versions:
                    repos = set(repo_ver['dist_repo_ids'] + [repo_ver['repo_id']])
                    # check whether any resources are not migrated and need a task
                    if repos.intersection(repos_ids_to_check):
                        needs_a_task = True
                if needs_a_task:
                    task_args = [plugin, pulp3_repo_setup, repo_name]
                    complex_repo_migration(*task_args)

        task_group = TaskGroup.current()
        progress_rv = task_group.group_progress_reports.filter(code='create.repo_version')
        progress_rv.update(total=F('total') + repo_ver_to_create)
        progress_dist = task_group.group_progress_reports.filter(
            code='create.distribution'
        )
        progress_dist.update(total=F('total') + dist_to_create)


def create_repo_version(progress_rv, pulp2_repo, pulp3_remote=None):
    """
    Create a repo version based on a pulp2 repository.

    Add a remote to a corresponding pulp 2 repository. Since any remote can change without a repo
    being changed itself, re-set it here for every repo.

    Args:
        progress_rv: GroupProgressReport queryset for repo_version creation
        pulp2_repo(Pulp2Repository): a pre-migrated repository to create a repo version for
        pulp3_remote(remote): a pulp3 remote
    """
    def detect_path_overlap(paths):
        """
        Check for valid POSIX paths (ie ones that aren't duplicated and don't overlap).

        Overlapping paths are where one path terminates inside another (e.g. a/b and a/b/c).

        NOTE: The logic is copied from pulpcore.app.files.validate_file_paths().

        This function returns the first dupe or overlap it detects. We use a trie (or
        prefix tree) to keep track of which paths we've already seen.

        Args:
            paths (iterable of str): An iterable of strings each representing a relative path

        Returns:
            str: a path which overlaps or duplicates another

        """
        path_trie = StringTrie(separator="/")
        for path in paths:
            if path in path_trie:
                # path duplicates a path already in the trie
                return path

            if path_trie.has_subtrie(path):
                # overlap where path is 'a/b' and trie has 'a/b/c'
                return path

            prefixes = list(path_trie.prefixes(path))
            if prefixes:
                # overlap where path is 'a/b/c' and trie has 'a/b'
                return path

            # if there are no overlaps, add it to our trie and continue
            path_trie[path] = True

    def resolve_path_overlap(version):
        """
        Remove content for which path overlaps some other.

        If it's a duplicated path, remove the older content.

        If something is absolutely wrong and we were not able to resolve conflicts,
        repo version creation will fail later.

        Paths can be overlapping because of an old Pulp 2 bug.

        Args:
            version(pulpcore.app.model.RepositoryVersion): incomplete version which needs path
                overlap resolution

        """
        paths = ContentArtifact.objects.filter(content__pk__in=version.content).values_list(
            "relative_path", flat=True
        )
        paths = list(paths)
        max_conflicts = version.content.count() - 1

        # Making it a for loop and not a while loop, just to be on the safe side.
        # It will loop only as many times as there are conflicts in paths.
        for i in range(max_conflicts):
            bad_path = detect_path_overlap(paths)
            if not bad_path:
                # no path overlaps, we are good
                break

            # Content Artifacts with conflicting relative paths ordered by pulp2 creation time
            cas_with_conflicts = ContentArtifact.objects.filter(
                content__pk__in=version.content, relative_path=bad_path
            ).order_by('-content__pulp2content__pulp2_last_updated')

            conflict_count = cas_with_conflicts.count()
            if conflict_count > 1:
                # There are duplicated paths and we need to keep the newest content in the version.
                # The query result is ordered desc by time so we remove all but the first content.
                content_to_remove = [ca.content.pk for ca in cas_with_conflicts[1:]]
                version.remove_content(Content.objects.filter(pk__in=content_to_remove))
                # exclude the duplicated paths from further search
                removed_count = conflict_count - 1
                _logger.info(
                    _(
                        'Duplicated paths have been found in Pulp 3 repo `{repo}`: {path}. '
                        'Removed: {num}.'
                    ).format(repo=version.repository.name, path=bad_path, num=removed_count)
                )
                for j in range(removed_count):
                    paths.remove(bad_path)
            else:
                # It's not a duplicated path but it overlaps with some other in the version,
                # it should be removed from the version to resolve the conflict.
                version.remove_content(cas_with_conflicts[0].content)
                _logger.info(
                    _(
                        'Overlapping paths have been found in Pulp 3 repo `{repo}`: Removed '
                        'content with {path} path.'
                    ).format(repo=version.repository.name, path=bad_path)
                )
                # exclude the resolved path from further search
                paths.remove(bad_path)

    if pulp3_remote:
        pulp2_repo.pulp3_repository_remote = pulp3_remote
        pulp2_repo.save()

    if pulp2_repo.is_migrated:
        progress_rv.update(total=F('total') - 1)
        return

    pulp3_repo = pulp2_repo.pulp3_repository
    unit_ids = Pulp2RepoContent.objects.filter(pulp2_repository=pulp2_repo).values_list(
        'pulp2_unit_id', flat=True)
    incoming_content = set(
        Pulp2Content.objects.filter(
            Q(pulp2_id__in=unit_ids) & (Q(pulp2_repo=None) | Q(pulp2_repo=pulp2_repo)),
        ).only('pulp3_content').values_list('pulp3_content__pk', flat=True)
    )

    with pulp3_repo.new_version() as new_version:
        repo_content = set(new_version.content.values_list('pk', flat=True))
        to_add = incoming_content - repo_content
        to_delete = repo_content - incoming_content
        new_version.add_content(Content.objects.filter(pk__in=to_add))
        new_version.remove_content(Content.objects.filter(pk__in=to_delete))
        resolve_path_overlap(new_version)

    is_empty_repo = not pulp2_repo.pulp3_repository_version
    if new_version.complete:
        pulp2_repo.pulp3_repository_version = new_version
        progress_rv.update(done=F('done') + 1)
    elif is_empty_repo:
        pulp2_repo.pulp3_repository_version = pulp3_repo.latest_version()
        progress_rv.update(done=F('done') + 1)
    else:
        progress_rv.update(total=F('total') - 1)
    pulp2_repo.is_migrated = True
    pulp2_repo.save()


def migrate_repo_distributor(dist_migrator, progress_dist, pulp2dist, repo_version=None):
    """
    Migrate repo distributor.

    Args:
        dist_migrator(Pulp2to3Distributor): distributor migrator class
        progress_dist: GroupProgressReport queryset for distribution creation
        pulp2dist(Pulp2Distributor): a pre-migrated distributor to migrate
        repo_version(RepositoryVersion): a pulp3 repo version
    """

    publication, distribution, created = dist_migrator.migrate_to_pulp3(
        pulp2dist, repo_version)
    if publication:
        pulp2dist.pulp3_publication = publication
    pulp2dist.pulp3_distribution = distribution
    pulp2dist.is_migrated = True
    pulp2dist.save()
    progress_dist.update(done=F('done') + 1)
    # CreatedResource were added  here because publications and repo versions
    # were listed among created resources and distributions were not. it could
    # create some confusion remotes are not listed still
    # TODO figure out what to do to make the output consistent
    if created:
        resource = CreatedResource(content_object=distribution)
        resource.save()
