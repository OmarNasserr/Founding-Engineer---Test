from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import (
    Survey, Section, Field,
    Respondent, SurveyResponse, FieldResponse, ExportReport,
)


# ── Inlines ───────────────────────────────────────────────────────────────────

class FieldInline(admin.StackedInline):
    model = Field
    extra = 0
    ordering = ('order',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    fields = (
        ('label', 'field_type', 'order'),
        ('is_required', 'is_sensitive', 'maps_to'),
        'options',
        'validation_rules',
        'conditions',
    )


class SectionInline(admin.StackedInline):
    model = Section
    extra = 0
    show_change_link = True
    ordering = ('order',)
    readonly_fields = ('id', 'field_count', 'created_at', 'updated_at')
    fields = ('title', 'order', 'conditions', 'field_count')

    @admin.display(description=_('Fields'))
    def field_count(self, obj):
        return obj.fields.count()


class FieldResponseInline(admin.TabularInline):
    model = FieldResponse
    extra = 0
    readonly_fields = ('field', 'value', 'created_at')
    fields = ('field', 'value')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# ── Survey ────────────────────────────────────────────────────────────────────

@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ('title', 'status_badge', 'created_by', 'section_count', 'total_field_count', 'total_response_count', 'created_at')
    list_filter = ('status', 'created_by')
    search_fields = ('title', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    inlines = [SectionInline]
    fieldsets = (
        (None, {
            'fields': ('id', 'title', 'description', 'status', 'created_by'),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description=_('Status'))
    def status_badge(self, obj):
        colors = {'draft': '#6c757d', 'published': '#28a745', 'archived': '#dc3545'}
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:4px;font-size:11px;font-weight:600">{}</span>',
            color, obj.get_status_display(),
        )

    @admin.display(description=_('Sections'))
    def section_count(self, obj):
        return obj.sections.count()

    @admin.display(description=_('Fields'))
    def total_field_count(self, obj):
        return Field.objects.filter(section__survey=obj).count()

    @admin.display(description=_('Responses'))
    def total_response_count(self, obj):
        return obj.responses.count()


# ── Section — hidden from nav, reachable via the Survey inline change link ────

@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'survey', 'order', 'field_count', 'has_conditions')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('survey', 'order')
    inlines = [FieldInline]
    fieldsets = (
        (None, {
            'fields': ('id', 'survey', 'title', 'order', 'conditions'),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_model_perms(self, request):
        # Hides Section from the admin sidebar/index while keeping the
        # change view accessible via the Survey inline "Change" link.
        return {}

    @admin.display(description=_('Fields'))
    def field_count(self, obj):
        return obj.fields.count()

    @admin.display(boolean=True, description=_('Has Conditions'))
    def has_conditions(self, obj):
        return bool(obj.conditions)


# ── Respondent ────────────────────────────────────────────────────────────────

@admin.register(Respondent)
class RespondentAdmin(admin.ModelAdmin):
    list_display = ('short_token', 'full_name', 'email', 'phone', 'response_count', 'created_at')
    search_fields = ('full_name', 'email', 'phone', 'session_token')
    readonly_fields = ('id', 'session_token', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    fieldsets = (
        (None, {
            'fields': ('id', 'session_token'),
        }),
        (_('Profile'), {
            'fields': ('full_name', 'email', 'phone'),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description=_('Session Token'))
    def short_token(self, obj):
        token = str(obj.session_token)
        return token[:8] + '…'

    @admin.display(description=_('Responses'))
    def response_count(self, obj):
        return obj.responses.count()


# ── Survey Response ───────────────────────────────────────────────────────────

@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = ('id_short', 'survey', 'respondent', 'status_badge', 'started_at', 'submitted_at')
    list_filter = ('status', 'survey')
    search_fields = ('survey__title', 'respondent__email', 'respondent__full_name')
    readonly_fields = (
        'id', 'survey', 'respondent', 'status',
        'started_at', 'submitted_at', 'last_saved_at',
        'created_at', 'updated_at',
    )
    ordering = ('-started_at',)
    date_hierarchy = 'started_at'
    inlines = [FieldResponseInline]
    fieldsets = (
        (None, {
            'fields': ('id', 'survey', 'respondent', 'status'),
        }),
        (_('Timing'), {
            'fields': ('started_at', 'submitted_at', 'last_saved_at'),
        }),
    )

    @admin.display(description=_('ID'))
    def id_short(self, obj):
        return str(obj.id)[:8] + '…'

    @admin.display(description=_('Status'))
    def status_badge(self, obj):
        colors = {'in_progress': '#e67e22', 'completed': '#28a745'}
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:4px;font-size:11px;font-weight:600">{}</span>',
            color, obj.get_status_display(),
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True


# ── Export Report ─────────────────────────────────────────────────────────────

@admin.register(ExportReport)
class ExportReportAdmin(admin.ModelAdmin):
    list_display = ('id_short', 'survey', 'requested_by', 'status_badge', 'file_path', 'created_at')
    list_filter = ('status',)
    search_fields = ('survey__title', 'requested_by__email')
    readonly_fields = (
        'id', 'survey', 'requested_by', 'file_path', 'status',
        'created_at', 'updated_at',
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    fieldsets = (
        (None, {
            'fields': ('id', 'survey', 'requested_by', 'status', 'file_path'),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description=_('ID'))
    def id_short(self, obj):
        return str(obj.id)[:8] + '…'

    @admin.display(description=_('Status'))
    def status_badge(self, obj):
        colors = {'pending': '#e67e22', 'ready': '#28a745', 'failed': '#dc3545'}
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:4px;font-size:11px;font-weight:600">{}</span>',
            color, obj.get_status_display(),
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True
