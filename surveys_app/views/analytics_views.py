import json
from collections import defaultdict

from django.conf import settings
from django.db.models import Count
from rest_framework import generics
from rest_framework.response import Response
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend

from helper_files.redis_client import REDIS_CLIENT
from helper_files.status_code import StatusCode
from helper_files.permissions import IsAnalyst, IsDataViewer, Permissions
from helper_files.pagination_helper import PaginationHelper
from helper_files.custom_exceptions import SurveyNotFoundException
from surveys_app.models import Survey, Field, SurveyResponse, FieldResponse, ExportReport, ExportStatus
from surveys_app.tasks import export_survey_responses_csv
from surveys_app.schemas import survey_analytics_schema, survey_export_schema, survey_export_list_schema


@survey_analytics_schema
class SurveyAnalytics(generics.GenericAPIView):
    """GET /api/v1/surveys/{survey_id}/analytics/ — response statistics for a survey."""

    permission_classes = [IsDataViewer]
    serializer_class = None

    def permission_denied(self, request, message=None, code=None):
        return Permissions.permission_denied(self, request)

    def get(self, request, *args, **kwargs):
        survey_id = self.kwargs.get('survey_id')
        survey = Survey.objects.filter(id=survey_id).first()
        if not survey:
            raise SurveyNotFoundException()

        cache_key = f'analytics:{survey_id}'
        cached = REDIS_CLIENT.get(cache_key)
        if cached:
            return Response(data=json.loads(cached), status=StatusCode.success)

        # Compute analytics
        total_responses = SurveyResponse.objects.filter(survey=survey).count()
        completed = SurveyResponse.objects.filter(survey=survey, status='completed').count()
        completion_rate = round((completed / total_responses * 100), 2) if total_responses else 0

        # Per-field value distributions (for choice fields only)
        choice_fields = list(Field.objects.filter(
            section__survey=survey,
            field_type__in=['dropdown', 'radio', 'checkbox']
        ))
        choice_field_ids = [f.id for f in choice_fields]
        all_field_responses = FieldResponse.objects.filter(
            field_id__in=choice_field_ids
        ).values('field_id', 'value')

        # Aggregate in Python
        response_by_field = defaultdict(dict)
        for fr in all_field_responses:
            fid = str(fr['field_id'])
            val = fr['value']
            response_by_field[fid][val] = response_by_field[fid].get(val, 0) + 1

        field_distributions = {}
        for field in choice_fields:
            field_distributions[str(field.id)] = {
                'label': field.label,
                'distribution': response_by_field.get(str(field.id), {}),
            }

        data = {
            'survey_id': str(survey_id),
            'total_responses': total_responses,
            'completed_responses': completed,
            'completion_rate': completion_rate,
            'field_distributions': field_distributions,
        }
        REDIS_CLIENT.setex(cache_key, 300, json.dumps(data, default=str))
        return Response(data=data, status=StatusCode.success)


@survey_export_schema
class SurveyExport(generics.GenericAPIView):
    """POST /api/v1/surveys/{survey_id}/analytics/export/ — queue a CSV export Celery task."""

    permission_classes = [IsAnalyst]
    serializer_class = None

    def permission_denied(self, request, message=None, code=None):
        return Permissions.permission_denied(self, request)

    def post(self, request, *args, **kwargs):
        survey_id = self.kwargs.get('survey_id')
        survey = Survey.objects.filter(id=survey_id).first()
        if not survey:
            raise SurveyNotFoundException()

        export_report = ExportReport.objects.create(
            survey=survey,
            requested_by=request.user,
            status=ExportStatus.PENDING,
        )
        export_survey_responses_csv.delay(
            survey_id=str(survey_id),
            requested_by_id=str(request.user.id),
            export_report_id=str(export_report.id),
        )
        return Response(
            data={
                'message': _('Export task queued.'),
                'status': StatusCode.success,
                'export_report_id': str(export_report.id),
            },
            status=StatusCode.success,
        )


@survey_export_list_schema
class SurveyExportList(generics.ListAPIView):
    """GET /api/v1/dashboard/surveys/{survey_id}/analytics/reports/ — list ExportReport records for a survey."""

    permission_classes = [IsDataViewer]
    pagination_class = PaginationHelper
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {'status': ['exact'], 'requested_by__email': ['exact']}

    def permission_denied(self, request, message=None, code=None):
        return Permissions.permission_denied(self, request)

    def get_queryset(self):
        survey_id = self.kwargs.get('survey_id')
        survey = Survey.objects.filter(id=survey_id).first()
        if not survey:
            raise SurveyNotFoundException()
        return ExportReport.objects.filter(survey=survey).select_related('requested_by').order_by('-created_at')

    def _build_file_url(self, request, file_path):
        if not file_path:
            return ''
        media_root = str(settings.MEDIA_ROOT)
        if file_path.startswith(media_root):
            relative = file_path[len(media_root):].lstrip('/')
            return request.build_absolute_uri(f'{settings.MEDIA_URL}{relative}')
        return file_path

    def get(self, request, *args, **kwargs):
        PaginationHelper.set_default_page_number_and_page_size(request)
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        data = [
            {
                'id': str(r.id),
                'status': r.status,
                'requested_by': r.requested_by.email if r.requested_by_id else None,
                'file_url': self._build_file_url(request, r.file_path),
                'created_at': r.created_at.isoformat(),
            }
            for r in (page if page is not None else queryset)
        ]
        if page is not None:
            return self.get_paginated_response(data)
        return Response(data={'results': data, 'status': StatusCode.success}, status=StatusCode.success)
