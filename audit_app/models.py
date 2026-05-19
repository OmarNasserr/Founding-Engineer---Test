from django.db import models


class AuditLog(models.Model):
    actor = models.ForeignKey('accounts_app.User', on_delete=models.SET_NULL,
                              null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=100)
    resource_id = models.CharField(max_length=255)
    payload = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['actor']),
            models.Index(fields=['action']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['resource_type', 'resource_id']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} by {self.actor} at {self.timestamp}"
