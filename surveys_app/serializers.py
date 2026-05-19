from rest_framework import serializers

from helper_files.serializer_helper import SerializerHelper
from surveys_app.models import Field, Section, Survey


class FieldWriteSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=False)  # optional — for identifying existing fields on update

    class Meta:
        model = Field
        fields = ['id', 'label', 'field_type', 'order', 'options',
                  'validation_rules', 'is_required', 'is_sensitive', 'maps_to', 'conditions']

    def is_valid(self, *, raise_exception=False):
        return SerializerHelper.is_valid(self=self, raise_exception=raise_exception)


class SectionWriteSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=False)  # optional — for identifying existing sections on update
    fields = FieldWriteSerializer(many=True, required=False, default=list)

    class Meta:
        model = Section
        fields = ['id', 'title', 'order', 'conditions', 'fields']

    def is_valid(self, *, raise_exception=False):
        return SerializerHelper.is_valid(self=self, raise_exception=raise_exception)


class SurveySerializer(serializers.ModelSerializer):
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    sections = SectionWriteSerializer(many=True, required=False, default=list)

    class Meta:
        model = Survey
        fields = ['id', 'title', 'description', 'status', 'created_by', 'sections', 'created_at']
        extra_kwargs = {
            'id': {'read_only': True},
            'created_at': {'read_only': True},
            'status': {'required': False},
        }

    def is_valid(self, *, raise_exception=False):
        return SerializerHelper.is_valid(self=self, raise_exception=raise_exception)


class SectionSerializer(serializers.ModelSerializer):
    survey = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Section
        fields = ['id', 'survey', 'title', 'order', 'conditions', 'created_at']
        extra_kwargs = {
            'id': {'read_only': True},
            'created_at': {'read_only': True},
        }

    def is_valid(self, *, raise_exception=False):
        return SerializerHelper.is_valid(self=self, raise_exception=raise_exception)


class FieldSerializer(serializers.ModelSerializer):
    section = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Field
        fields = [
            'id', 'section', 'label', 'field_type', 'order',
            'options', 'validation_rules', 'is_required', 'is_sensitive',
            'maps_to', 'conditions', 'created_at',
        ]
        extra_kwargs = {
            'id': {'read_only': True},
            'created_at': {'read_only': True},
        }

    def is_valid(self, *, raise_exception=False):
        return SerializerHelper.is_valid(self=self, raise_exception=raise_exception)


class FieldDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Field
        fields = [
            'id', 'label', 'field_type', 'order',
            'options', 'validation_rules', 'is_required', 'is_sensitive',
            'maps_to', 'conditions',
        ]
        extra_kwargs = {
            'id': {'read_only': True},
            'label': {'read_only': True},
            'field_type': {'read_only': True},
            'order': {'read_only': True},
            'options': {'read_only': True},
            'validation_rules': {'read_only': True},
            'is_required': {'read_only': True},
            'is_sensitive': {'read_only': True},
            'maps_to': {'read_only': True},
            'conditions': {'read_only': True},
        }

    def is_valid(self, *, raise_exception=False):
        return SerializerHelper.is_valid(self=self, raise_exception=raise_exception)


class SectionDetailSerializer(serializers.ModelSerializer):
    fields = FieldDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Section
        fields = ['id', 'title', 'order', 'conditions', 'fields']
        extra_kwargs = {
            'id': {'read_only': True},
            'title': {'read_only': True},
            'order': {'read_only': True},
            'conditions': {'read_only': True},
        }

    def is_valid(self, *, raise_exception=False):
        return SerializerHelper.is_valid(self=self, raise_exception=raise_exception)


class SurveyDetailSerializer(serializers.ModelSerializer):
    sections = SectionDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Survey
        fields = ['id', 'title', 'description', 'status', 'sections']
        extra_kwargs = {
            'id': {'read_only': True},
            'title': {'read_only': True},
            'description': {'read_only': True},
            'status': {'read_only': True},
        }

    def is_valid(self, *, raise_exception=False):
        return SerializerHelper.is_valid(self=self, raise_exception=raise_exception)


class FieldResponseSerializer(serializers.Serializer):
    field_id = serializers.UUIDField()
    value = serializers.CharField()

    def is_valid(self, *, raise_exception=False):
        return SerializerHelper.is_valid(self=self, raise_exception=raise_exception)


class RespondentAnswersSerializer(serializers.Serializer):
    answers = FieldResponseSerializer(many=True, required=False, default=list)

    def is_valid(self, *, raise_exception=False):
        return SerializerHelper.is_valid(self=self, raise_exception=raise_exception)
