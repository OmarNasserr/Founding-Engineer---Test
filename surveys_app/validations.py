from django.utils.translation import gettext_lazy as _
from rest_framework.response import Response

from helper_files.status_code import StatusCode


class SurveyValidations:

    @staticmethod
    def validate_survey_create(data, valid, err) -> Response:
        """Args: data (dict), valid (bool), err (str). Returns: Response."""
        if not valid:
            return Response(
                data={'message': err, 'status': StatusCode.bad_request},
                status=StatusCode.bad_request,
            )
        return Response(
            data={'message': _('Survey created successfully.'), 'status': StatusCode.created},
            status=StatusCode.created,
        )

    @staticmethod
    def validate_survey_update(data, valid, err) -> Response:
        """Args: data (dict), valid (bool), err (str). Returns: Response."""
        if not valid:
            return Response(
                data={'message': err, 'status': StatusCode.bad_request},
                status=StatusCode.bad_request,
            )
        return Response(
            data={'message': _('Survey updated successfully.'), 'status': StatusCode.success},
            status=StatusCode.success,
        )


class ResponseValidations:

    @staticmethod
    def validate_partial_save(data, valid, err):
        """Args: data, valid (bool), err (str). Returns: Response."""
        if not valid:
            return Response(
                data={'message': err, 'status': StatusCode.bad_request},
                status=StatusCode.bad_request
            )
        return Response(
            data={'message': _('Progress saved.'), 'status': StatusCode.success},
            status=StatusCode.success
        )

    @staticmethod
    def validate_final_submit(data, valid, err, active_fields=None, answers_dict=None):
        """Args: data, valid (bool), err (str), active_fields (list of Field instances),
        answers_dict (dict of field_id str -> value, optional). Returns: Response.
        Checks all required active fields have a value."""
        if not valid:
            return Response(
                data={'message': err, 'status': StatusCode.bad_request},
                status=StatusCode.bad_request
            )
        if active_fields:
            # Use answers_dict if provided, else fall back to parsing data['answers']
            if answers_dict is None:
                answers_dict = {str(a.get('field_id', '')): a.get('value') for a in (data.get('answers') or [])}
            for field in active_fields:
                if field.is_required and not answers_dict.get(str(field.id)):
                    return Response(
                        data={
                            'message': _(f'Field "{field.label}" is required.'),
                            'status': StatusCode.bad_request
                        },
                        status=StatusCode.bad_request
                    )
        return Response(
            data={'message': _('Survey submitted successfully.'), 'status': StatusCode.success},
            status=StatusCode.success
        )
