from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver


@receiver(pre_save, sender='surveys_app.Survey')
def on_survey_pre_save(sender, instance, **kwargs):
    # Store previous status directly on the instance so post_save can read it
    # without a module-level dict. Both signals fire on the same instance object
    # within the same request, so this is safe in multi-pod environments.
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._pre_save_status = old.status
        except sender.DoesNotExist:
            instance._pre_save_status = None
    else:
        instance._pre_save_status = None


@receiver(post_save, sender='surveys_app.Survey')
def on_survey_save(sender, instance, created, **kwargs):
    from audit_app.models import AuditLog

    if created:
        action = 'survey.created'
    elif instance.status == 'published':
        prev_status = getattr(instance, '_pre_save_status', None)
        if prev_status == 'published':
            return  # already was published — not a transition
        action = 'survey.published'
    else:
        return  # no audit log for other (non-publish) updates

    actor = kwargs.get('actor') or getattr(instance, 'created_by', None)

    AuditLog.objects.create(
        actor=actor,
        action=action,
        resource_type='Survey',
        resource_id=str(instance.id),
        payload={'title': instance.title, 'status': instance.status},
    )


@receiver(post_delete, sender='surveys_app.Survey')
def on_survey_delete(sender, instance, **kwargs):
    from audit_app.models import AuditLog

    actor = kwargs.get('actor') or getattr(instance, 'created_by', None)

    AuditLog.objects.create(
        actor=actor,
        action='survey.deleted',
        resource_type='Survey',
        resource_id=str(instance.id),
        payload={'title': instance.title, 'status': instance.status},
    )


@receiver(post_save, sender='surveys_app.ExportReport')
def on_export_report_create(sender, instance, created, **kwargs):
    from audit_app.models import AuditLog

    if not created:
        return

    AuditLog.objects.create(
        actor=instance.requested_by,
        action='survey.export_triggered',
        resource_type='Survey',
        resource_id=str(instance.survey_id),
        payload={'survey_id': str(instance.survey_id), 'export_report_id': str(instance.id)},
    )


@receiver(post_save, sender='surveys_app.SurveyResponse')
def on_survey_response_save(sender, instance, created, **kwargs):
    from audit_app.models import AuditLog

    # Only log when a response transitions to completed (not on initial creation)
    if created or instance.status != 'completed':
        return

    actor = kwargs.get('actor')

    AuditLog.objects.create(
        actor=actor,
        action='response.submitted',
        resource_type='SurveyResponse',
        resource_id=str(instance.id),
        payload={
            'survey_id': str(instance.survey_id),
            'respondent_id': str(instance.respondent_id),
        },
    )

