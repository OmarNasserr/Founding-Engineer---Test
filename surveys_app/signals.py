import logging

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from helper_files.redis_client import REDIS_CLIENT

logger = logging.getLogger(__name__)


@receiver(post_save, sender='surveys_app.Survey')
@receiver(post_delete, sender='surveys_app.Survey')
def invalidate_survey_cache_on_survey(sender, instance, **kwargs):
    REDIS_CLIENT.delete(f'survey:{instance.id}')


@receiver(post_save, sender='surveys_app.Section')
@receiver(post_delete, sender='surveys_app.Section')
def invalidate_survey_cache_on_section(sender, instance, **kwargs):
    REDIS_CLIENT.delete(f'survey:{instance.survey_id}')


@receiver(post_save, sender='surveys_app.Field')
@receiver(post_delete, sender='surveys_app.Field')
def invalidate_survey_cache_on_field(sender, instance, **kwargs):
    try:
        REDIS_CLIENT.delete(f'survey:{instance.section.survey_id}')
    except Exception as e:
        logger.warning(f'Cache invalidation failed for Field {instance.id}: {e}')
