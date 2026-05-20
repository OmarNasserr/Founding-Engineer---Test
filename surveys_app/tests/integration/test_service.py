from datetime import datetime, timedelta, timezone

import jwt
import pytest
from django.conf import settings

from helper_files.custom_exceptions import InvalidSessionTokenException
from surveys_app.service import RespondentService


pytestmark = pytest.mark.django_db


def test_decode_valid_token(draft_survey):
    respondent, token = RespondentService.create_session(draft_survey)

    respondent_id, survey_id = RespondentService.decode_session(token)

    assert respondent_id == str(respondent.id)
    assert survey_id == str(draft_survey.id)


def test_decode_expired_token(draft_survey):
    expired_token = jwt.encode(
        {
            "respondent_id": "respondent-id",
            "survey_id": str(draft_survey.id),
            "exp": datetime.now(tz=timezone.utc) - timedelta(minutes=1),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )

    with pytest.raises(InvalidSessionTokenException):
        RespondentService.decode_session(expired_token)


def test_decode_tampered_token(draft_survey):
    _, token = RespondentService.create_session(draft_survey)
    tampered_token = token[:-8] + ('b' * 8)

    with pytest.raises(InvalidSessionTokenException):
        RespondentService.decode_session(tampered_token)
