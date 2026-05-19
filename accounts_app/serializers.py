from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from accounts_app.models import User, UserRole
from helper_files.serializer_helper import SerializerHelper


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    role = serializers.ChoiceField(choices=UserRole.choices, default=UserRole.DATA_VIEWER, required=False)

    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'role']

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(_('A user with this email already exists.'))
        return value

    def is_valid(self, *, raise_exception=False):
        return SerializerHelper.is_valid(self=self, raise_exception=raise_exception)

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def is_valid(self, *, raise_exception=False):
        return SerializerHelper.is_valid(self=self, raise_exception=raise_exception)
