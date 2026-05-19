from django.urls import path
from surveys_app.views import (
    # Builder
    SurveyListCreate,
    SurveyRetrieveUpdateDestroy,
    SurveyFieldsList,
    SurveyPublish,
    # Respondent
    SurveyPublicDetail,
    RespondentSessionCreate,
    RespondentSessionDetail,
    RespondentSubmit,
    # Analytics
    SurveyAnalytics,
    SurveyExport,
    SurveyExportList,
)

# Public respondent-facing URLs — mounted at /api/v1/surveys/
public_urlpatterns = [
    path('<uuid:survey_id>/', SurveyPublicDetail.as_view(), name='survey-public-detail'),
    path('<uuid:survey_id>/respond/', RespondentSessionCreate.as_view(), name='respondent-session-create'),
    path('<uuid:survey_id>/respond/<str:session_token>/', RespondentSessionDetail.as_view(), name='respondent-session-detail'),
    path('submit/<str:session_token>/', RespondentSubmit.as_view(), name='respondent-submit'),
]

# Dashboard URLs — mounted at /api/v1/dashboard/surveys/
dashboard_urlpatterns = [
    path('', SurveyListCreate.as_view(), name='survey-list-create'),
    path('<uuid:survey_id>/', SurveyRetrieveUpdateDestroy.as_view(), name='survey-detail'),
    path('<uuid:survey_id>/fields/', SurveyFieldsList.as_view(), name='survey-fields-list'),
    path('<uuid:survey_id>/publish/', SurveyPublish.as_view(), name='survey-publish'),
    path('<uuid:survey_id>/analytics/', SurveyAnalytics.as_view(), name='survey-analytics'),
    path('<uuid:survey_id>/analytics/export/', SurveyExport.as_view(), name='survey-export-trigger'),
    path('<uuid:survey_id>/analytics/reports/', SurveyExportList.as_view(), name='survey-reports-list'),
]
