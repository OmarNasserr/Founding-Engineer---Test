from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as _BaseTokenRefreshView
from django.utils.translation import gettext_lazy as _
from helper_files.status_code import StatusCode
from helper_files.permissions import Permissions
from accounts_app.models import User
from accounts_app.serializers import RegisterSerializer, LoginSerializer
from accounts_app.validations import AccountValidations
from accounts_app.schemas import register_schema, login_schema, token_refresh_schema


@register_schema
class RegisterView(generics.GenericAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def permission_denied(self, request, message=None, code=None):
        return Permissions.permission_denied(self, request)


    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        valid, err = serializer.is_valid()
        response = AccountValidations.validate_register(request.data, valid, err)
        if response.status_code == StatusCode.created:
            instance = serializer.save()
            response.data.update(self.get_serializer(instance).data)
        return response


@login_schema
class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    def permission_denied(self, request, message=None, code=None):
        return Permissions.permission_denied(self, request)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        valid, err = serializer.is_valid()
        user = None
        if valid:
            email = serializer.validated_data.get('email')
            password = serializer.validated_data.get('password')
            db_user = User.objects.filter(email=email).first()
            if db_user and db_user.check_password(password):
                user = db_user
        response = AccountValidations.validate_login(request.data, valid, err, user=user)
        if response.status_code == StatusCode.success:
            refresh = RefreshToken.for_user(user)
            response.data.update({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            })
        return response


@token_refresh_schema
class TokenRefreshView(_BaseTokenRefreshView):
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
