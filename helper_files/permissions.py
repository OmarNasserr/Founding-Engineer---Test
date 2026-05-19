from rest_framework.permissions import BasePermission
from helper_files.custom_exceptions import PermissionDenied, NotAuthenticated


class Permissions:

    def permission_denied(self, request, message=None, code=None):
        if request.authenticators and not request.successful_authenticator:
            raise NotAuthenticated()
        raise PermissionDenied()

    def check_object_permissions(self, request, obj):
        for permission in self.get_permissions():
            if not permission.has_object_permission(request, self, obj):
                self.permission_denied(request)


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'admin')


class IsAnalyst(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in ('admin', 'analyst'))


class IsDataViewer(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
