import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from helper_files.status_code import StatusCode

logger = logging.getLogger(__name__)


def global_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        return response

    logger.error(f'Unhandled exception: {exc}', exc_info=True)
    return Response(
        data={'message': 'An unexpected error occurred.', 'status': StatusCode.internal_server_err},
        status=StatusCode.internal_server_err,
    )
