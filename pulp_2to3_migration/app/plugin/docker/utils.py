from django.conf import settings
from pulp_2to3_migration.app.constants import DEFAULT_BATCH_SIZE
from . import pulp2_models


def find_tags():
    """
    Find tags that have same name within the repo.
    Return only one tag out of 2 tags with the same name.
    Prefer schema2 over schema1.
    """

    batch_size = settings.CONTENT_PREMIGRATION_BATCH_SIZE or DEFAULT_BATCH_SIZE

    # sort the schema version in desc mode.
    sort_stage = {"$sort": {"schema_version": -1}}
    # group tags by name and repo_id; take just first result out of the 2 tags with the same name
    group_stage = {
        "$group": {
            "_id": {"name": "$name", "repo_id": "$repo_id"},
            "tags_id": {"$first": "$_id"},
        }
    }
    # get only the require field to minimize the result BSON size
    project_stage = {"$project": {"_id": 0, "tags_id": 1}}
    result = pulp2_models.Tag.objects.aggregate(
        [sort_stage, group_stage, project_stage], allowDiskUse=True
    ).batch_size(batch_size)

    tags_ids = set([])
    for tag in result:
        tags_ids.add(tag["tags_id"])

    return list(tags_ids)
