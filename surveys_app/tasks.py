import csv
import os
import logging
from datetime import datetime

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def export_survey_responses_csv(self, survey_id, requested_by_id, export_report_id):
    """
    Args: survey_id (str UUID), requested_by_id (str UUID), export_report_id (str UUID).
    Exports all completed SurveyResponse rows for the survey to CSV.
    Updates the pre-created ExportReport record on completion or final failure.
    """
    from surveys_app.models import Survey, SurveyResponse, Field, ExportReport, ExportStatus
    from surveys_app.service import decrypt_value

    export_report = ExportReport.objects.filter(id=export_report_id).first()

    try:
        survey = Survey.objects.get(id=survey_id)

        # Gather all completed responses
        responses = SurveyResponse.objects.filter(
            survey=survey,
            status='completed',
        ).select_related('respondent').prefetch_related(
            'field_responses__field'
        )

        # Collect all unique fields across the survey (ordered by section then field order)
        fields = Field.objects.filter(
            section__survey=survey
        ).order_by('section__order', 'order')
        field_list = list(fields)
        field_headers = [f.label for f in field_list]
        field_id_map = {str(f.id): f for f in field_list}

        # Prepare output directory
        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports', str(survey_id))
        os.makedirs(export_dir, exist_ok=True)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        file_path = os.path.join(export_dir, f'{timestamp}.csv')

        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # Header row
            writer.writerow(['response_id', 'respondent_id', 'submitted_at'] + field_headers)

            for response in responses:
                # Build a field_id → value map for this response
                answer_map = {}
                for fr in response.field_responses.all():
                    field = field_id_map.get(str(fr.field_id))
                    if field and field.is_sensitive:
                        answer_map[str(fr.field_id)] = decrypt_value(fr.value)
                    else:
                        answer_map[str(fr.field_id)] = fr.value

                row = [
                    str(response.id),
                    str(response.respondent_id),
                    response.submitted_at.isoformat() if response.submitted_at else '',
                ] + [answer_map.get(str(f.id), '') for f in field_list]
                writer.writerow(row)

        # Update ExportReport record to READY
        if export_report:
            export_report.file_path = file_path
            export_report.status = ExportStatus.READY
            export_report.save(update_fields=['file_path', 'status'])

        logger.info(f'Export completed for survey {survey_id}: {file_path}')
        return file_path

    except Exception as exc:
        logger.error(f'Export task failed for survey {survey_id}: {exc}', exc_info=True)
        if self.request.retries >= self.max_retries:
            if export_report:
                export_report.status = ExportStatus.FAILED
                export_report.save(update_fields=['status'])
            raise
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
