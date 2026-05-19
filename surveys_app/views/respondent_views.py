import json

from django.db.models import Prefetch
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils.translation import gettext_lazy as _

from helper_files.redis_client import REDIS_CLIENT
from helper_files.status_code import StatusCode
from helper_files.permissions import Permissions
from helper_files.custom_exceptions import (
    SurveyNotFoundException, AlreadySubmittedException, InvalidSessionTokenException,
)
from surveys_app.models import Survey, Section, Field, SurveyResponse, FieldResponse
from surveys_app.serializers import SurveyDetailSerializer, RespondentAnswersSerializer
from surveys_app.validations import ResponseValidations
from surveys_app.service import RespondentService, decrypt_value
from surveys_app.logic import ConditionalLogicEngine
from surveys_app.schemas import (
    survey_public_detail_schema, respondent_session_create_schema,
    respondent_session_detail_schema, respondent_submit_schema,
)


@survey_public_detail_schema
class SurveyPublicDetail(generics.RetrieveAPIView):
    """GET /api/v1/surveys/{survey_id}/ — public survey detail (no auth required)."""

    permission_classes = [AllowAny]
    serializer_class = SurveyDetailSerializer

    def permission_denied(self, request, message=None, code=None):
        return Permissions.permission_denied(self, request)

    def retrieve(self, request, *args, **kwargs):
        survey_id = self.kwargs.get('survey_id')
        cache_key = f'survey:{survey_id}'

        cached = REDIS_CLIENT.get(cache_key)
        if cached:
            return Response(data=json.loads(cached), status=StatusCode.success)

        survey = Survey.objects.prefetch_related(
            Prefetch('sections', queryset=Section.objects.order_by('order').prefetch_related(
                Prefetch('fields', queryset=Field.objects.order_by('order'))
            ))
        ).filter(id=survey_id, status='published').first()
        if not survey:
            raise SurveyNotFoundException()

        data = SurveyDetailSerializer(survey).data
        REDIS_CLIENT.setex(cache_key, 3600, json.dumps(data, default=str))
        return Response(data=data, status=StatusCode.success)


@respondent_session_create_schema
class RespondentSessionCreate(generics.GenericAPIView):
    """POST /api/v1/surveys/{survey_id}/respond/ — create session, optionally save first answers."""

    permission_classes = [AllowAny]
    serializer_class = RespondentAnswersSerializer

    def permission_denied(self, request, message=None, code=None):
        return Permissions.permission_denied(self, request)


    def post(self, request, *args, **kwargs):
        survey_id = self.kwargs.get('survey_id')
        survey = Survey.objects.filter(id=survey_id, status='published').first()
        if not survey:
            raise SurveyNotFoundException()

        serializer = self.get_serializer(data=request.data)
        valid, err = serializer.is_valid()
        response = ResponseValidations.validate_partial_save(request.data, valid, err)
        if response.status_code != StatusCode.success:
            return response

        respondent, token = RespondentService.create_session(survey)
        survey_response = SurveyResponse.objects.create(
            survey=survey,
            respondent=respondent,
        )
        answers = serializer.validated_data.get('answers', [])
        if answers:
            RespondentService.save_partial(survey_response, answers)

        return Response(
            data={
                'message': _('Session started.'),
                'status': StatusCode.success,
                'session_token': token,
                'survey_response_id': str(survey_response.id),
            },
            status=StatusCode.success,
        )


@respondent_session_detail_schema
class RespondentSessionDetail(generics.GenericAPIView):
    """
    GET  /api/v1/surveys/{survey_id}/respond/{session_token}/ — resume: return saved answers + status.
    POST /api/v1/surveys/{survey_id}/respond/{session_token}/ — autosave partial answers.
    AllowAny.
    """

    permission_classes = [AllowAny]
    serializer_class = RespondentAnswersSerializer

    def permission_denied(self, request, message=None, code=None):
        return Permissions.permission_denied(self, request)

    def _get_survey_response(self, session_token, survey_id):
        """Args: session_token (str), survey_id (str). Returns: SurveyResponse instance."""
        respondent_id, token_survey_id = RespondentService.decode_session(session_token)
        if str(token_survey_id) != str(survey_id):
            raise InvalidSessionTokenException()
        survey_response = SurveyResponse.objects.select_related(
            'survey', 'respondent'
        ).filter(
            respondent_id=respondent_id,
            survey_id=survey_id,
        ).first()
        if not survey_response:
            raise InvalidSessionTokenException()
        return survey_response

    def get(self, request, *args, **kwargs):
        survey_id = self.kwargs.get('survey_id')
        session_token = self.kwargs.get('session_token')
        survey_response = self._get_survey_response(session_token, survey_id)

        field_responses = FieldResponse.objects.filter(
            survey_response=survey_response
        ).select_related('field')

        answers = []
        for fr in field_responses:
            value = fr.value
            if fr.field.is_sensitive:
                value = decrypt_value(value)
            answers.append({'field_id': str(fr.field_id), 'value': value})

        return Response(data={
            'status': survey_response.status,
            'last_saved_at': survey_response.last_saved_at,
            'answers': answers,
        }, status=StatusCode.success)

    def post(self, request, *args, **kwargs):
        survey_id = self.kwargs.get('survey_id')
        session_token = self.kwargs.get('session_token')
        survey_response = self._get_survey_response(session_token, survey_id)

        if survey_response.status == 'completed':
            raise AlreadySubmittedException()

        serializer = RespondentAnswersSerializer(data=request.data)
        valid, err = serializer.is_valid()
        response = ResponseValidations.validate_partial_save(request.data, valid, err)
        if response.status_code != StatusCode.success:
            return response

        answers = serializer.validated_data.get('answers', [])
        RespondentService.save_partial(survey_response, answers)
        return response


@respondent_submit_schema
class RespondentSubmit(generics.GenericAPIView):
    """POST /api/v1/surveys/submit/{session_token}/ — final submission."""

    permission_classes = [AllowAny]
    serializer_class = RespondentAnswersSerializer

    def permission_denied(self, request, message=None, code=None):
        return Permissions.permission_denied(self, request)


    def post(self, request, *args, **kwargs):
        session_token = self.kwargs.get('session_token')
        respondent_id, survey_id = RespondentService.decode_session(session_token)

        survey_response = SurveyResponse.objects.select_related(
            'survey', 'respondent'
        ).filter(
            respondent_id=respondent_id,
            survey_id=survey_id,
        ).first()
        if not survey_response:
            raise InvalidSessionTokenException()

        if survey_response.status == 'completed':
            raise AlreadySubmittedException()

        serializer = RespondentAnswersSerializer(data=request.data)
        valid, err = serializer.is_valid()

        # Load existing stored answers
        stored = {
            str(fr.field_id): fr.value
            for fr in FieldResponse.objects.filter(survey_response=survey_response)
        }
        # Parse current request answers
        answers_list = []
        if valid:
            answers_list = serializer.validated_data.get('answers', [])
        # Build merged answers dict (current request overrides stored)
        merged_answers_dict = dict(stored)
        for a in answers_list:
            merged_answers_dict[str(a['field_id'])] = a['value']

        engine = ConditionalLogicEngine()
        active_fields = engine.get_active_fields(survey_response.survey, merged_answers_dict)

        response = ResponseValidations.validate_final_submit(
            request.data, valid, err,
            active_fields=active_fields,
            answers_dict=merged_answers_dict,
        )
        if response.status_code != StatusCode.success:
            return response

        RespondentService.submit(survey_response, answers_list, active_fields)
        return response
