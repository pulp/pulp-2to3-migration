from django.contrib.postgres.fields import JSONField
from django.db import models

from pulpcore.app.models import (  # it has to be imported directly from pulpcore see #5353
    Remote,
)
from pulpcore.plugin.models import (
    BaseModel,
    BaseDistribution,
    Repository,
    RepositoryVersion,
    Publication,
)


class Pulp2Repository(BaseModel):
    """
    Information about Pulp 2 repository.

    Fields:
        pulp2_repo_id (models.TextField): Repository ID in Pulp 2
        pulp2_object_id (models.CharField): Object id of a repository in Pulp 2
        pulp2_description (models.TextField): Description of a repository in Pulp 2
        pulp2_last_unit_added (models.DateTimeField): Last time a unit was added to
            a repository in Pulp 2
        pulp2_last_unit_removed (models.DateTimeField): Last time a unit was removed from
            a repository in Pulp 2
        is_migrated (models.BooleanField): True if a resource has been migrated to Pulp 3; False
            if it's never been migrated or if it's been updated since the last migration run.
        not_in_plan (models.BooleanField): True if a resource is not a part of the migration plan.
        pulp2_repo_type (models.CharField): repo type in Pulp 2

    Relations:
        pulp3_repository_version (models.ForeignKey): Pulp 3 repository version which Pulp 2
            repository was migrated to
        pulp3_repository_remote (models.ForeignKey): Pulp 3 remote to use with the migrated Pulp2
    """
    pulp2_object_id = models.CharField(max_length=255, unique=True)
    pulp2_repo_id = models.TextField()
    pulp2_description = models.TextField(null=True)
    pulp2_last_unit_added = models.DateTimeField(null=True)
    pulp2_last_unit_removed = models.DateTimeField(null=True)
    is_migrated = models.BooleanField(default=False)
    not_in_plan = models.BooleanField(default=False)
    pulp2_repo_type = models.CharField(max_length=25)

    # This needs to be a foreign key to cover a case when repository in pulp 2 was removed after
    # a migration run and then recreated with exactly the same name and content in pulp 2,
    # and then migration was run again. In Pulp 3 it's the same repo and repo version which
    # should point to a new pulp2repository object.
    pulp3_repository_version = models.ForeignKey(RepositoryVersion,
                                                 on_delete=models.SET_NULL,
                                                 null=True)

    # The same importer/remote can be used for multiple repositories, thus it's a foreign key.
    pulp3_repository_remote = models.ForeignKey(Remote,
                                                on_delete=models.SET_NULL,
                                                null=True)

    # This is needed for migrating Variants of the DistributionTree
    pulp3_repository = models.ForeignKey(Repository,
                                         on_delete=models.SET_NULL,
                                         null=True)

    class Meta:
        indexes = [
            models.Index(fields=['pulp2_repo_type']),
        ]


class Pulp2RepoContent(BaseModel):
    """
    Information about content in Pulp 2 repository.

    It's important to use a relation to Pulp 2 repository and not just Pulp 2 repo_id because
    over time repository with the same id can be removed and created again in Pulp 2 and
    the migration plugin needs to distinguish between those.

    Fields:
        pulp2_unit_id (models.CharField): Unit_id in Pulp 2
        pulp2_content_type_id (models.CharField): Id of a content type in Pulp 2

    Relations:
        pulp2_repository (models.ForeignKey): Pulp 2 repository this content belongs to
    """
    pulp2_unit_id = models.CharField(max_length=255)
    pulp2_content_type_id = models.CharField(max_length=255)
    pulp2_created = models.DateTimeField(null=True)
    pulp2_updated = models.DateTimeField(null=True)

    pulp2_repository = models.ForeignKey(Pulp2Repository, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('pulp2_repository', 'pulp2_unit_id')
        indexes = [
            models.Index(fields=['pulp2_content_type_id']),
        ]


class Pulp2Importer(BaseModel):
    """
    Information about Pulp 2 importer.

    Fields:
        pulp2_object_id (models.CharField): Object id of an importer in Pulp 2
        pulp2_type_id (models.CharField): Id of importer type in Pulp 2
        pulp2_config (JSONField): Pulp 2 importer config in JSON format
        pulp2_last_updated (models.DateTimeField): Last time the importer was updated
        pulp2_repo_id (models.TextField): Id of a repo in Pulp 2 an importer belongs to
        is_migrated (models.BooleanField): True if a resource has been migrated to Pulp 3; False
            if it's never been migrated or if it's been updated since the last migration run.
        not_in_plan (models.BooleanField): True if a resource is not a part of the migration plan.

    Relations:
        pulp2_repository (models.OneToOneField): Pulp 2 repository this importer belongs to
        pulp3_remote (models.OneToOneField): Pulp 3 remote which this importer was migrated to
    """
    pulp2_object_id = models.CharField(max_length=255, unique=True)
    pulp2_type_id = models.CharField(max_length=255)
    pulp2_config = JSONField()
    pulp2_last_updated = models.DateTimeField()
    pulp2_repo_id = models.TextField()
    is_migrated = models.BooleanField(default=False)
    not_in_plan = models.BooleanField(default=False)

    pulp2_repository = models.OneToOneField(Pulp2Repository, on_delete=models.CASCADE, null=True)
    pulp3_remote = models.OneToOneField(Remote, on_delete=models.SET_NULL, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['pulp2_type_id']),
        ]


class Pulp2Distributor(BaseModel):
    """
    Information about Pulp 2 distributor.

    Fields:
        pulp2_object_id (models.CharField): Object id of a distributor in Pulp 2
        pulp2_id (models.TextField): Id of distributor in Pulp 2
        pulp2_type_id (models.CharField): Id of distributor type in Pulp 2
        pulp2_config (JSONField): Pulp 2 distributor config in JSON format
        pulp2_last_updated (models.DateTimeField): Last time the distributor was updated
        pulp2_repo_id (models.TextField): Id of a repo in Pulp 2 a distributor belongs to
        is_migrated (models.BooleanField): True if a resource has been migrated to Pulp 3; False
            if it's never been migrated or if it's been updated since the last migration run.
        not_in_plan (models.BooleanField): True if a resource is not a part of the migration plan.

    Relations:
        pulp2_repos (models.ManyToManyField): Pulp 2 repository that is getting distributed
        pulp3_publication (models.ForeignKey): Pulp 3 publication this distributor was
            migrated to
        pulp3_distribution (models.OneToOneField): Pulp 3 distribution this distributor was
            migrated to
    """
    pulp2_object_id = models.CharField(max_length=255, unique=True)
    pulp2_id = models.TextField()
    pulp2_type_id = models.CharField(max_length=255)
    pulp2_config = JSONField()
    pulp2_last_updated = models.DateTimeField()
    pulp2_repo_id = models.TextField()
    is_migrated = models.BooleanField(default=False)
    not_in_plan = models.BooleanField(default=False)

    # each pulp2 repository can have multiple distributors
    pulp2_repos = models.ManyToManyField(Pulp2Repository, related_name='pulp2_dists')

    # the same publication/repo version can be published by multiple distributors
    pulp3_publication = models.ForeignKey(Publication, on_delete=models.SET_NULL, null=True)

    # due to base_path overlap restriction, a distribution can't correspond to multiple pulp 2
    # distributors, thus one-to-one relationship.
    pulp3_distribution = models.OneToOneField(BaseDistribution,
                                              on_delete=models.SET_NULL,
                                              null=True)

    class Meta:
        unique_together = ('pulp2_object_id',)
        indexes = [
            models.Index(fields=['pulp2_type_id']),
        ]
