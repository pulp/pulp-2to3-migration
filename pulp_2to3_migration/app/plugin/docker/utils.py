from . import pulp2_models


def find_tags():
    """
    Find tags that have same name within the repo.
    Return only one tag out of 2 tags with the same name.
    Prefer schema2 over schema1.
    """

    # sort the schema version in desc mode.
    sort_stage = {'$sort': {'schema_version': -1}}
    # group tags by name and repo_id; take just first result out of the 2 tags with the same name
    group_stage1 = {'$group': {'_id': {'name': '$name', 'repo_id': '$repo_id'},
                    'tags_id': {'$first': '$_id'}}}
    group_stage2 = {'$group': {'_id': None, 'tags_ids': {'$addToSet': '$tags_id'}}}
    result = pulp2_models.Tag.objects.aggregate([sort_stage, group_stage1, group_stage2])
    if result._has_next():
        return result.next()['tags_ids']
    return []
