import logging

from pulpcore.plugin.models import ProgressReport

from pulp_2to3_migration.app.models import (
    MigrationPlan,
    Pulp2Content,
    Pulp2Distributor,
    Pulp2Importer,
    Pulp2LazyCatalog,
    Pulp2RepoContent,
    Pulp2Repository,
)


_logger = logging.getLogger(__name__)


def reset_pulp3_data(migration_plan_pk):
    """
    A task to reset data in Pulp 3 for the plugins specified in a migration plan.

    It also removes all the pre-migrated data. This enables the migration being from scratch and
    not the incremental one for the specified set of plugins.

    Args:
        migration_plan_pk (str): The migration plan PK.

    """
    plan = MigrationPlan.objects.get(pk=migration_plan_pk)
    pulp2_plugins = plan.get_plugins()
    pb_data = dict(message="Resetting data for Pulp 3 plugins", code="reset.pulp3.data",
                   total=len(pulp2_plugins))
    with ProgressReport(**pb_data) as pb:
        for plugin in plan.get_plugin_plans():
            for dist_migrator in plugin.migrator.distributor_migrators.values():
                for dist_model in dist_migrator.pulp3_distribution_models:
                    dist_model.objects.all().only('pk').delete()
                for pub_model in dist_migrator.pulp3_publication_models:
                    pub_model.objects.all().only('pk').delete()

            for imp_migrator in plugin.migrator.importer_migrators.values():
                for remote_model in imp_migrator.pulp3_remote_models:
                    remote_model.objects.all().only('pk').delete()

            repo_model = plugin.migrator.pulp3_repository
            if hasattr(repo_model, 'sub_repo'):
                # sub_repos can't be deleted until the content referring to them is not removed
                repo_model.objects.filter(sub_repo=False).only('pk').delete()
            else:
                repo_model.objects.all().only('pk').delete()

            for content_model in repo_model.CONTENT_TYPES:
                content_model.objects.all().only('pk').delete()

            if hasattr(repo_model, 'sub_repo'):
                # after content is removed we can delete the remaining repositories
                repo_model.objects.all().only('pk').delete()

            pb.increment()

    pb_data = dict(message="Removing pre-migrated data", code="reset.premigrated.data", total=1)
    with ProgressReport(**pb_data) as pb:
        for plugin in plan.get_plugin_plans():
            for content_type, pulp2to3_content_model in plugin.migrator.content_models.items():
                pulp2to3_content_model.objects.all().only('pk').delete()
                Pulp2Content.objects.filter(pulp2_content_type_id=content_type).only('pk').delete()
                Pulp2LazyCatalog.objects.filter(
                    pulp2_content_type_id=content_type
                ).only('pk').delete()
                Pulp2RepoContent.objects.filter(
                    pulp2_content_type_id=content_type
                ).only('pk').delete()
            for importer_type in plugin.migrator.importer_migrators:
                Pulp2Importer.objects.filter(pulp2_type_id=importer_type).only('pk').delete()
            for dist_type in plugin.migrator.distributor_migrators:
                Pulp2Distributor.objects.filter(pulp2_type_id=dist_type).only('pk').delete()
            Pulp2Repository.objects.filter(
                pulp2_repo_type=plugin.migrator.pulp2_plugin
            ).only('pk').delete()
            pb.increment()
