from django.contrib.postgres.fields import JSONField
from django.db import models

from pulpcore.app.models import (  # it has to be imported directly from pulpcore see #5353
    Remote,
    Publisher,
)
from pulpcore.plugin.models import (
    Model,
    BaseDistribution,
    RepositoryVersion,
    Publication,
)


class Pulp2Repository(Model):
    """
    Information about Pulp 2 repository.

    Fields:
        pulp2_repo_id (models.CharField): Repository ID in Pulp 2
        pulp2_object_id (models.CharField): Object id of a repository in Pulp 2
        pulp2_last_unit_added (models.DateTimeField): Last time a unit was added to
            a repository in Pulp 2
        pulp2_last_unit_removed (models.DateTimeField): Last time a unit was removed from
            a repository in Pulp 2

    Relations:
        pulp3_repository_version (models.OneToOneField): Pulp 3 repository version which Pulp 2
            repository was migrated to
    """
    pulp2_object_id = models.CharField(max_length=255, unique=True)
    pulp2_repo_id = models.CharField(max_length=255)  # in Pulp2 it might be longer?
    pulp2_last_unit_added = models.DateTimeField(null=True)
    pulp2_last_unit_removed = models.DateTimeField(null=True)

    pulp3_repository_version = models.OneToOneField(RepositoryVersion,
                                                    on_delete=models.SET_NULL,
                                                    null=True)


class Pulp2RepoContent(Model):
    """
    Information about content in Pulp 2 repository.

    It's important to use a relation to Pulp 2 repository and not just Pulp 2 repo_id because
    over time repository with the same id can be removed and created again in Pulp 2 and
    the migration plugin needs to distinguish between those.

    Fields:
        pulp2_unit_id (models.CharField): Repository id in Pulp 2
        pulp2_content_type_id (models.CharField): Id of a content type in Pulp 2

    Relations:
        pulp2_repository (models.ForeignKey): Pulp 2 repository this content belongs to
    """
    pulp2_unit_id = models.CharField(max_length=255)
    pulp2_content_type_id = models.CharField(max_length=255)

    pulp2_repository = models.ForeignKey(Pulp2Repository, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('pulp2_repository', 'pulp2_unit_id')


class Pulp2Importer(Model):
    """
    Information about Pulp 2 importer.

    Fields:
       pulp2_type_id (models.CharField): Id of importer type in Pulp 2
       pulp2_config (JSONField): Pulp 2 importer config in JSON format
       pulp2_last_updated (models.DateTimeField): Last time the importer was updated

    Relations:
        pulp2_repository (models.OneToOneField): Pulp 2 repository this importer belongs to
        pulp3_remote (models.OneToOneField): Pulp 3 remote which this importer was migrated to
    """
    pulp2_type_id = models.CharField(max_length=255)
    pulp2_config = JSONField()
    pulp2_last_updated = models.DateTimeField()

    pulp2_repository = models.OneToOneField(Pulp2Repository, on_delete=models.CASCADE)
    pulp3_remote = models.OneToOneField(Remote, on_delete=models.SET_NULL, null=True)


class Pulp2Distributor(Model):
    """
    Information about Pulp 2 distributor.

    Fields:
       pulp2_id (models.CharField): Id of distributor in Pulp 2
       pulp2_type_id (models.CharField): Id of distributor type in Pulp 2
       pulp2_config (JSONField): Pulp 2 distributor config in JSON format
       pulp2_auto_publish (models.BooleanField): A flag to determine if auto-publish is enabled
       pulp2_last_updated (models.DateTimeField): Last time the distributor was updated

    Relations:
        pulp2_repository (models.ForeignKey): Pulp 2 repository this distributor belongs to
        pulp3_publisher(models.OneToOneField): Pulp 3 publisher this distributor was migrated to
        pulp3_publication (models.OneToOneField): Pulp 3 publication this distributor was
            migrated to
        pulp3_distribution (models.OneToOneField): Pulp 3 distribution this distributor was
            migrated to
    """
    pulp2_id = models.CharField(max_length=255)  # in Pulp2 it might be longer?
    pulp2_type_id = models.CharField(max_length=255)
    pulp2_config = JSONField()
    pulp2_auto_publish = models.BooleanField()
    pulp2_last_updated = models.DateTimeField()

    pulp2_repository = models.ForeignKey(Pulp2Repository, on_delete=models.CASCADE)
    pulp3_publisher = models.OneToOneField(Publisher, on_delete=models.SET_NULL, null=True)
    pulp3_publication = models.OneToOneField(Publication, on_delete=models.SET_NULL, null=True)
    pulp3_distribution = models.OneToOneField(BaseDistribution,
                                              on_delete=models.SET_NULL,
                                              null=True)

    class Meta:
        unique_together = ('pulp2_repository', 'pulp2_id')
