import logging

from django.db.models import Q

from pulpcore.plugin.models import (
    Content,
    CreatedResource,
    ProgressReport,
    Repository,
    Task,
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


def migrate_content(plan):
    """
    A coroutine to initiate content migration for each plugin.

    Args:
         plan (MigrationPlan): Migration Plan to use
    """
    progress_data = dict(message='Migrating content to Pulp 3', code='migrating.content', total=0)
    with ProgressReport(**progress_data) as pb:
        # schedule content migration into Pulp 3 using pre-migrated Pulp 2 content
        for plugin in plan.get_plugin_plans():
            plugin.migrator.migrate_content_to_pulp3()

            # only used for progress bar counters
            content_types = plugin.migrator.content_models.keys()
            pulp2content_qs = Pulp2Content.objects.filter(pulp2_content_type_id__in=content_types,
                                                          pulp3_content=None)
            pb.total += pulp2content_qs.count()
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

            # TODO: Should we filter out repos which have is_migrated=True?
            pulp2repos_qs = Pulp2Repository.objects.filter(
                pulp3_repository_version=None,
                not_in_plan=False,
                pulp2_repo_type=plugin.type,
            )
            repos_to_create = plugin.get_repo_creation_setup()

            # no specific migration plan for repositories
            if not repos_to_create:
                pb.total += pulp2repos_qs.count()
                pb.save()

                for pulp2repo in pulp2repos_qs:
                    pulp3_repo_name = pulp2repo.pulp2_repo_id
                    repository_class = plugin.migrator.pulp3_repository
                    repo, created = repository_class.objects.get_or_create(
                        name=pulp3_repo_name,
                        defaults={'description': pulp2repo.pulp2_description})
                    if not pulp2repo.pulp3_repository:
                        pulp2repo.pulp3_repository = repo
                        pulp2repo.save()
                    if created:
                        pb.increment()
                    else:
                        pb.total -= 1
                        pb.save()

            # specific migration plan for repositories
            else:
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
                    pulp2repos_qs = Pulp2Repository.objects.filter(pulp2_repo_id__in=pulp2_repo_ids)
                    for pulp2repo in pulp2repos_qs:
                        if not pulp2repo.pulp3_repository:
                            pulp2repo.pulp3_repository = repo
                            pulp2repo.save()
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


def simple_plugin_migration(plugin):
    """Migrate everything for a given plugin.

    Args:
        plugin: Plugin object
        pb: A progress report object
    """
    distributor_migrators = plugin.migrator.distributor_migrators
    distributor_types = list(plugin.migrator.distributor_migrators.keys())
    pulp2distributors_qs = Pulp2Distributor.objects.filter(
        pulp3_distribution=None,
        pulp3_publication=None,
        not_in_plan=False,
        pulp2_type_id__in=distributor_types
    )
    repos_to_migrate = Pulp2Repository.objects.filter(pulp2_repo_type=plugin.type,
                                                      not_in_plan=False)
    for pulp2_repo in repos_to_migrate:
        # Create one repo version for each pulp 2 repo if needed.
        create_repo_version(plugin.migrator, pulp2_repo)
    for pulp2_dist in pulp2distributors_qs:
        dist_migrator = distributor_migrators.get(pulp2_dist.pulp2_type_id)
        migrate_repo_distributor(dist_migrator, pulp2_dist)


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
    pulp2_importer_repo_id = \
        pulp3_repo_setup[repo_name].get('pulp2_importer_repository_id')
    if pulp2_importer_repo_id:
        try:
            pulp2_importer = Pulp2Importer.objects.get(
                pulp2_repo_id=pulp2_importer_repo_id,
                not_in_plan=False
            )
            pulp3_remote = pulp2_importer.pulp3_remote
        except Pulp2Importer.DoesNotExist:
            pass
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
            create_repo_version(plugin.migrator, pulp2_repo, pulp3_remote)

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
            for dist in pulp2dist:
                dist_migrator = distributor_migrators.get(dist.pulp2_type_id)
                migrate_repo_distributor(
                    dist_migrator, dist,
                    migrated_repo.pulp3_repository_version
                )


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
        pulp3_repo_setup = plugin.get_repo_creation_setup()

        if not pulp3_repo_setup:
            task_func = simple_plugin_migration
            task_args = [plugin]
            task_func(*task_args)
        else:
            task_func = complex_repo_migration

            if parallel:
                for repo_name in pulp3_repo_setup:
                    repo = Repository.objects.get(name=repo_name).cast()
                    task_args = [plugin, pulp3_repo_setup, repo_name]
                    enqueue_with_reservation(
                        task_func,
                        [repo],
                        args=task_args,
                        task_group=Task.current().task_group
                    )
            else:
                # Serial (non-parallel)
                for repo_name in pulp3_repo_setup:
                    task_args = [plugin, pulp3_repo_setup, repo_name]
                    task_func(*task_args)


def create_repo_version(migrator, pulp2_repo, pulp3_remote=None):
    """
    Create a repo version based on a pulp2 repository.

    Add a remote to a corresponding pulp 2 repository. Since any remote can change without a repo
    being changed itself, re-set it here for every repo.

    Args:
        migrator: migrator to use, provides repo type information
        pulp2_repo(Pulp2Repository): a pre-migrated repository to create a repo version for
        pulp3_remote(remote): a pulp3 remote
    """

    if pulp3_remote:
        pulp2_repo.pulp3_repository_remote = pulp3_remote
    # pulp2importer might not be migrated, e.g. config was empty
    elif hasattr(pulp2_repo, 'pulp2importer'):
        pulp2_repo.pulp3_repository_remote = pulp2_repo.pulp2importer.pulp3_remote
    if pulp2_repo.is_migrated:
        pulp2_repo.save()
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
    if new_version.complete:
        pulp2_repo.pulp3_repository_version = new_version
    if not pulp2_repo.pulp3_repository_version:
        pulp2_repo.pulp3_repository_version = pulp3_repo.latest_version()
    pulp2_repo.is_migrated = True
    pulp2_repo.save()


def migrate_repo_distributor(dist_migrator, pulp2dist, repo_version=None):
    """
    Migrate repo distributor.

    Args:
        dist_migrator(Pulp2to3Distributor): distributor migrator class
        pulp2dist(Pulp2Distributor): a pre-migrated distributor to migrate
        repo_version(RepositoryVersion): a pulp3 repo version
    """

    publication, distribution, created = dist_migrator.migrate_to_pulp3(
        pulp2dist, repo_version)
    if publication:
        pulp2dist.pulp3_publication = publication
    if distribution:
        pulp2dist.pulp3_distribution = distribution
    pulp2dist.is_migrated = True
    pulp2dist.save()
    # CreatedResource were added  here because publications and repo versions
    # were listed among created resources and distributions were not. it could
    # create some confusion remotes are not listed still
    # TODO figure out what to do to make the output consistent
    if created:
        resource = CreatedResource(content_object=distribution)
        resource.save()
