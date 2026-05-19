from rest_framework.exceptions import APIException
from helper_files.status_code import StatusCode


class PermissionDenied(APIException):
    status_code = StatusCode.forbidden
    default_detail = {'message': 'You do not have permission to perform this action.', 'status': StatusCode.forbidden}
    default_code = 'permission_denied'


class NotAuthenticated(APIException):
    status_code = StatusCode.unauthorized
    default_detail = {'message': 'Authentication credentials were not provided.', 'status': StatusCode.unauthorized}
    default_code = 'not_authenticated'


class CustomException(APIException):
    status_code = StatusCode.bad_request
    default_code = 'error'

    def __init__(self, detail, status_code=None):
        if status_code is not None:
            self.status_code = status_code
        self.detail = {'message': detail, 'status': self.status_code}


class SurveyNotFoundException(CustomException):
    def __init__(self):
        super().__init__(detail='Survey not found.', status_code=StatusCode.not_found)


class SurveyNotPublishedException(CustomException):
    def __init__(self):
        super().__init__(detail='This survey is not published.', status_code=StatusCode.bad_request)


class AlreadySubmittedException(CustomException):
    def __init__(self):
        super().__init__(detail='You have already submitted this survey.', status_code=StatusCode.bad_request)


class InvalidSessionTokenException(CustomException):
    def __init__(self):
        super().__init__(detail='Session token is invalid or has expired.', status_code=StatusCode.unauthorized)
