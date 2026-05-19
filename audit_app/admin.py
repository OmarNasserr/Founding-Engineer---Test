from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'resource_type', 'resource_id', 'actor', 'timestamp')
    list_filter = ('action', 'resource_type')
    search_fields = ('actor__email', 'actor__username', 'action', 'resource_type', 'resource_id')
    readonly_fields = ('id', 'actor', 'action', 'resource_type', 'resource_id', 'payload', 'timestamp')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)

    fieldsets = (
        (None, {
            'fields': ('actor', 'action', 'resource_type', 'resource_id'),
        }),
        ('Payload', {
            'fields': ('payload',),
            'classes': ('collapse',),
        }),
        ('Timestamp', {
            'fields': ('timestamp',),
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True
