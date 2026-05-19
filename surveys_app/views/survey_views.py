from rest_framework import generics, filters
from rest_framework.response import Response
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend

from helper_files.status_code import StatusCode
from helper_files.permissions import IsAdmin, Permissions
from helper_files.pagination_helper import PaginationHelper
from helper_files.custom_exceptions import SurveyNotFoundException
from surveys_app.models import Survey, Field
from surveys_app.serializers import SurveySerializer, SurveyDetailSerializer
from surveys_app.validations import SurveyValidations
from surveys_app.service import SurveyService
from surveys_app.schemas import (
    survey_list_create_schema,
    survey_retrieve_update_destroy_schema,
    survey_fields_list_schema,
    survey_publish_schema,
)


@survey_list_create_schema
class SurveyListCreate(generics.ListCreateAPIView):
    queryset = Survey.objects.select_related('created_by').order_by('-created_at')
    serializer_class = SurveySerializer
    permission_classes = [IsAdmin]
    pagination_class = PaginationHelper
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = {'status': ['exact'], 'created_by__email': ['exact']}
    search_fields = ['title', 'description']

    def permission_denied(self, request, message=None, code=None):
        return Permissions.permission_denied(self, request)

    def get(self, request, *args, **kwargs):
        PaginationHelper.set_default_page_number_and_page_size(request)
        return super().get(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        valid, err = serializer.is_valid()
        response = SurveyValidations.validate_survey_create(request.data, valid, err)
        if response.status_code == StatusCode.created:
            serializer.validated_data['created_by'] = request.user
            instance = SurveyService.create_survey(serializer)
            response.data.update(self.get_serializer(instance).data)
        return response


@survey_retrieve_update_destroy_schema
class SurveyRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Survey.objects.select_related('created_by').all()
    serializer_class = SurveySerializer
    permission_classes = [IsAdmin]
    lookup_url_kwarg = 'survey_id'
    http_method_names = ['get', 'put', 'delete', 'head', 'options']

    def permission_denied(self, request, message=None, code=None):
        return Permissions.permission_denied(self, request)


    def get_object(self):
        obj_id = self.kwargs.get('survey_id')
        obj = self.get_queryset().filter(id=obj_id).first()
        if not obj:
            raise SurveyNotFoundException()
        return obj

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        from surveys_app.serializers import SurveyDetailSerializer
        return Response(
            data=SurveyDetailSerializer(instance).data,
            status=StatusCode.success,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=False)
        valid, err = serializer.is_valid()
        response = SurveyValidations.validate_survey_update(request.data, valid, err)
        if response.status_code == StatusCode.success:
            instance = SurveyService.update_survey(serializer)
            response.data.update(self.get_serializer(instance).data)
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            data={'message': _('Survey deleted successfully.'), 'status': StatusCode.success},
            status=StatusCode.success,
        )


@survey_fields_list_schema
class SurveyFieldsList(generics.GenericAPIView):
    """GET /api/v1/dashboard/surveys/{survey_id}/fields/ — flat ordered field list for conditions builder."""

    permission_classes = [IsAdmin]
    serializer_class = None

    def permission_denied(self, request, message=None, code=None):
        return Permissions.permission_denied(self, request)


    def get(self, request, *args, **kwargs):
        survey_id = self.kwargs.get('survey_id')
        survey = Survey.objects.filter(id=survey_id).first()
        if not survey:
            raise SurveyNotFoundException()

        fields = (
            Field.objects
            .filter(section__survey=survey)
            .select_related('section')
            .order_by('section__order', 'order')
        )

        data = [
            {
                'id': str(f.id),
                'label': f.label,
                'field_type': f.field_type,
                'options': f.options,
                'section_title': f.section.title,
                'section_order': f.section.order,
                'order': f.order,
            }
            for f in fields
        ]

        return Response(
            data={'status': StatusCode.success, 'fields': data},
            status=StatusCode.success,
        )


@survey_publish_schema
class SurveyPublish(generics.GenericAPIView):
    permission_classes = [IsAdmin]
    serializer_class = SurveySerializer
    lookup_url_kwarg = 'survey_id'

    def permission_denied(self, request, message=None, code=None):
        return Permissions.permission_denied(self, request)

    def get_queryset(self):
        return Survey.objects.select_related('created_by').all()

    def get_object(self):
        obj_id = self.kwargs.get('survey_id')
        obj = self.get_queryset().filter(id=obj_id).first()
        if not obj:
            raise SurveyNotFoundException()
        self.check_object_permissions(self.request, obj)
        return obj

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        survey = SurveyService.publish_survey(instance)
        return Response(
            data={'message': _('Survey published successfully.'), 'status': StatusCode.success, **self.get_serializer(survey).data},
            status=StatusCode.success,
        )
