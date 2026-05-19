from http import HTTPStatus


class StatusCode:
    success = HTTPStatus.OK
    created = HTTPStatus.CREATED
    bad_request = HTTPStatus.BAD_REQUEST
    unauthorized = HTTPStatus.UNAUTHORIZED
    forbidden = HTTPStatus.FORBIDDEN
    not_found = HTTPStatus.NOT_FOUND
    internal_server_err = HTTPStatus.INTERNAL_SERVER_ERROR
