from django_filters.rest_framework import filters
from gettext import gettext as _

from drf_spectacular.utils import extend_schema
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.serializers import ValidationError

from pulpcore.app.viewsets.base import DATETIME_FILTER_OPTIONS
from pulpcore.app.viewsets.custom_filters import (
    HyperlinkRelatedFilter,
    IsoDateTimeFilter
)

from pulpcore.plugin.models import Task
from pulpcore.plugin.serializers import AsyncOperationResponseSerializer
from pulpcore.plugin.tasking import enqueue_with_reservation
from pulpcore.plugin.viewsets import (
    BaseFilterSet,
    NamedModelViewSet,
    OperationPostponedResponse,
)

from .constants import PULP_2TO3_MIGRATION_RESOURCE
from .models import MigrationPlan, Pulp2Content, Pulp2Repository
from .serializers import (
    MigrationPlanSerializer,
    MigrationPlanRunSerializer,
    Pulp2ContentSerializer,
    Pulp2RepositoriesSerializer,
)
from .tasks import (
    migrate_from_pulp2,
    reset_pulp3_data,
)


def is_migration_plan_running():
    """
    Identify if any migration related task is running, including its child tasks.

    Returns:
         bool: True, if any related to the migration plan tasks are running; False, otherwise.

    """
    qs = Task.objects.filter(state__in=['waiting', 'running'],
                             reserved_resources_record__resource='pulp_2to3_migration')
    if qs:
        return True

    groups_with_running_tasks = Task.objects.filter(
        state__in=['waiting', 'running'],
        task_group__isnull=False).values_list('task_group_id', flat=True)
    groups_with_migration_tasks = Task.objects.filter(
        task_group__isnull=False,
        reserved_resources_record__resource='pulp_2to3_migration').values_list(
        'task_group_id', flat=True)
    if groups_with_running_tasks.intersection(groups_with_migration_tasks):
        return True

    return False


class MigrationPlanViewSet(NamedModelViewSet,
                           mixins.CreateModelMixin,
                           mixins.RetrieveModelMixin,
                           mixins.DestroyModelMixin,
                           mixins.ListModelMixin):
    """
    MigrationPlan ViewSet.
    """
    endpoint_name = 'migration-plans'
    queryset = MigrationPlan.objects.all()
    serializer_class = MigrationPlanSerializer

    @extend_schema(
        summary="Run migration plan",
        description="Trigger an asynchronous task to run a migration from Pulp 2.",
        responses={202: AsyncOperationResponseSerializer}
    )
    @action(detail=True, methods=('post',), serializer_class=MigrationPlanRunSerializer)
    def run(self, request, pk):
        """Run the migration plan."""
        migration_plan = self.get_object()
        serializer = MigrationPlanRunSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        validate = serializer.validated_data.get('validate', False)
        dry_run = serializer.validated_data.get('dry_run', False)
        skip_corrupted = serializer.validated_data.get('skip_corrupted', False)

        if is_migration_plan_running():
            raise ValidationError(_("Only one migration plan can run or be reset at a time"))

        result = enqueue_with_reservation(
            migrate_from_pulp2,
            [PULP_2TO3_MIGRATION_RESOURCE],
            kwargs={
                'migration_plan_pk': migration_plan.pk,
                'validate': validate,
                'dry_run': dry_run,
                'skip_corrupted': skip_corrupted
            }
        )
        return OperationPostponedResponse(result, request)

    @extend_schema(
        summary="Reset Pulp 3 data for plugins specified in the migration plan",
        description="Trigger an asynchronous task to remove data from Pulp 3 related to the "
                    "plugins specified in the migration plan.",
        responses={202: AsyncOperationResponseSerializer}
    )
    @action(detail=True, methods=('post',))
    def reset(self, request, pk):
        """Reset Pulp 3 data for plugins specified in the migration plan."""
        migration_plan = self.get_object()

        if is_migration_plan_running():
            raise ValidationError(_("Only one migration plan can run or be reset at a time"))

        result = enqueue_with_reservation(
            reset_pulp3_data,
            [PULP_2TO3_MIGRATION_RESOURCE],
            kwargs={
                'migration_plan_pk': migration_plan.pk,
            }
        )
        return OperationPostponedResponse(result, request)


class Pulp2ContentFilter(BaseFilterSet):
    """
    Filter for Pulp2Content ViewSet.
    """
    pulp2_id = filters.CharFilter()
    pulp2_content_type_id = filters.CharFilter()
    pulp2_last_updated = IsoDateTimeFilter(field_name='pulp2_last_updated')
    pulp3_content = HyperlinkRelatedFilter()

    class Meta:
        model = Pulp2Content
        fields = {
            'pulp2_id': ['exact', 'in'],
            'pulp2_content_type_id': ['exact', 'in'],
            'pulp2_last_updated': DATETIME_FILTER_OPTIONS,
            'pulp3_content': ['exact']
        }


class Pulp2ContentViewSet(NamedModelViewSet, mixins.RetrieveModelMixin, mixins.ListModelMixin):
    """
    ViewSet for Pulp2Content model.
    """
    endpoint_name = 'pulp2content'
    queryset = Pulp2Content.objects.all()
    serializer_class = Pulp2ContentSerializer
    filterset_class = Pulp2ContentFilter


class Pulp2RepositoriesFilter(BaseFilterSet):
    """
    Filter for Pulp2Repositories ViewSet.
    """
    pulp2_repo_id = filters.CharFilter()
    is_migrated = filters.BooleanFilter()
    not_in_plan = filters.BooleanFilter()

    class Meta:
        model = Pulp2Repository
        fields = {
            'pulp2_repo_id': ['exact', 'in'],
            'is_migrated': ['exact'],
            'not_in_plan': ['exact']
        }


class Pulp2RepositoriesViewSet(NamedModelViewSet, mixins.RetrieveModelMixin, mixins.ListModelMixin):
    """
    ViewSet for Pulp2Repositories model.
    """
    endpoint_name = 'pulp2repositories'
    queryset = Pulp2Repository.objects.all()
    serializer_class = Pulp2RepositoriesSerializer
    filterset_class = Pulp2RepositoriesFilter
