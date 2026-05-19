import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel


class SurveyStatus(models.TextChoices):
    DRAFT = 'draft', _('Draft')
    PUBLISHED = 'published', _('Published')
    ARCHIVED = 'archived', _('Archived')


class FieldType(models.TextChoices):
    TEXT = 'text', _('Text')
    TEXTAREA = 'textarea', _('Textarea')
    NUMBER = 'number', _('Number')
    DATE = 'date', _('Date')
    DATETIME = 'datetime', _('Datetime')
    EMAIL = 'email', _('Email')
    URL = 'url', _('URL')
    DROPDOWN = 'dropdown', _('Dropdown')
    RADIO = 'radio', _('Radio')
    CHECKBOX = 'checkbox', _('Checkbox')
    RATING = 'rating', _('Rating')


class MapsTo(models.TextChoices):
    RESPONDENT_FULL_NAME = 'respondent_full_name', _('Respondent Full Name')
    RESPONDENT_EMAIL = 'respondent_email', _('Respondent Email')
    RESPONDENT_PHONE = 'respondent_phone', _('Respondent Phone')


class SurveyResponseStatus(models.TextChoices):
    IN_PROGRESS = 'in_progress', _('In Progress')
    COMPLETED = 'completed', _('Completed')


class Survey(BaseModel):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=SurveyStatus.choices, default=SurveyStatus.DRAFT)
    created_by = models.ForeignKey('accounts_app.User', on_delete=models.SET_NULL,
                                   null=True, related_name='surveys')

    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_by']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return self.title


class Section(BaseModel):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='sections')
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField()
    conditions = models.JSONField(null=True, blank=True, default=None)

    class Meta:
        unique_together = [('survey', 'order')]
        indexes = [
            models.Index(fields=['survey']),
            models.Index(fields=['order']),
        ]

    def __str__(self):
        return f"{self.survey.title} - {self.title}"


class Field(BaseModel):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='fields')
    label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=20, choices=FieldType.choices)
    order = models.PositiveIntegerField()
    options = models.JSONField(null=True, blank=True, default=None)
    validation_rules = models.JSONField(null=True, blank=True, default=None)
    is_required = models.BooleanField(default=False)
    is_sensitive = models.BooleanField(default=False)
    maps_to = models.CharField(max_length=50, null=True, blank=True, choices=MapsTo.choices)
    conditions = models.JSONField(null=True, blank=True, default=None)

    class Meta:
        unique_together = [('section', 'order')]
        indexes = [
            models.Index(fields=['section']),
            models.Index(fields=['order']),
        ]

    def __str__(self):
        return f"{self.section.survey.title} - {self.label}"


class Respondent(BaseModel):
    session_token = models.UUIDField(unique=True, db_index=True, default=uuid.uuid4)
    full_name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return str(self.session_token)


class SurveyResponse(BaseModel):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='responses')
    respondent = models.ForeignKey(Respondent, on_delete=models.CASCADE, related_name='responses')
    status = models.CharField(max_length=20, choices=SurveyResponseStatus.choices,
                              default=SurveyResponseStatus.IN_PROGRESS)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    last_saved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('survey', 'respondent')]
        indexes = [
            models.Index(fields=['survey']),
            models.Index(fields=['respondent']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Response {self.id} for {self.survey.title}"


class FieldResponse(BaseModel):
    survey_response = models.ForeignKey(SurveyResponse, on_delete=models.CASCADE, related_name='field_responses')
    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name='responses')
    value = models.TextField()

    class Meta:
        indexes = [
            models.Index(fields=['survey_response', 'field']),
        ]

    def __str__(self):
        return f"FieldResponse {self.id}"


class ExportStatus(models.TextChoices):
    PENDING = 'pending', _('Pending')
    READY = 'ready', _('Ready')
    FAILED = 'failed', _('Failed')


class ExportReport(BaseModel):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='export_reports')
    requested_by = models.ForeignKey('accounts_app.User', on_delete=models.SET_NULL, null=True,
                                     related_name='export_reports')
    file_path = models.CharField(max_length=500, blank=True, default='')
    status = models.CharField(max_length=20, choices=ExportStatus.choices, default=ExportStatus.PENDING)

    class Meta:
        indexes = [
            models.Index(fields=['survey']),
            models.Index(fields=['status']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"ExportReport {self.id} for {self.survey.title}"
