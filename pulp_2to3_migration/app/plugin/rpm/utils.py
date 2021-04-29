from mongoengine.queryset.visitor import Q as mongo_Q

from .pulp2_models import YumMetadataFile


def exclude_unsupported_metadata():
    """
    Exclude .zck and .xz metadata from the list of content to premigrate.
    """
    exclude_zck = mongo_Q(data_type__not__endswith='_zck')
    exclude_xz = mongo_Q(data_type__not__endswith='_xz')
    supported_content = YumMetadataFile.objects.filter(exclude_zck & exclude_xz)
    return [c.id for c in supported_content]
