from django.utils.translation import gettext_lazy as _
from rest_framework.response import Response

from helper_files.status_code import StatusCode


class AccountValidations:

    @staticmethod
    def validate_register(data, valid, err):
        """Args: data (dict), valid (bool), err (str). Returns: Response."""
        if not valid:
            return Response(
                data={'message': err, 'status': StatusCode.bad_request},
                status=StatusCode.bad_request,
            )
        return Response(
            data={'message': _('Registered successfully'), 'status': StatusCode.created},
            status=StatusCode.created,
        )

    @staticmethod
    def validate_login(data, valid, err, user=None):
        """Args: data (dict), valid (bool), err (str), user (User|None). Returns: Response."""
        if not valid:
            return Response(
                data={'message': err, 'status': StatusCode.bad_request},
                status=StatusCode.bad_request,
            )
        if user is None:
            return Response(
                data={'message': _('Invalid email or password.'), 'status': StatusCode.unauthorized},
                status=StatusCode.unauthorized,
            )
        return Response(
            data={'message': _('Login successful.'), 'status': StatusCode.success},
            status=StatusCode.success,
        )
