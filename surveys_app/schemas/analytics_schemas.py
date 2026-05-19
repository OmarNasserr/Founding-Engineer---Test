from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiResponse, OpenApiExample, OpenApiParameter


survey_analytics_schema = extend_schema_view(
    get=extend_schema(
        summary='Get response analytics for a survey',
        description=(
            'Returns total and completed response counts, completion rate, and value distributions '
            'for choice fields (radio, dropdown, checkbox).\n\n'
            'Results are **Redis-cached for 5 minutes**.'
        ),
        tags=['Analytics & Exports'],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Analytics data with field distributions',
                examples=[
                    OpenApiExample(
                        'Survey analytics',
                        value={
                            'survey_id': 'b1c2d3e4-0000-0000-0000-000000000001',
                            'total_responses': 42,
                            'completed_responses': 35,
                            'completion_rate': 83.33,
                            'field_distributions': {
                                'e5f6a7b8-0000-0000-0000-000000000001': {
                                    'label': 'Do you own a car?',
                                    'distribution': {'Yes': 28, 'No': 14},
                                },
                                'a7b8c9d0-0000-0000-0000-000000000001': {
                                    'label': 'Car Brand',
                                    'distribution': {'Toyota': 12, 'Honda': 9, 'Ford': 7},
                                },
                            },
                        },
                    )
                ],
            ),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Analyst or Admin role required'),
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Survey not found',
                examples=[OpenApiExample('Not found', value={'message': 'Survey not found.', 'status': 404})],
            ),
        },
    )
)

survey_export_schema = extend_schema_view(
    post=extend_schema(
        summary='Trigger CSV export of survey responses',
        description=(
            'Queues a background Celery task to export all completed responses to a CSV file.\n\n'
            'Immediately creates an `ExportReport` with `status=pending` and returns its ID. '
            'Poll `GET /analytics/reports/` to check when the export transitions to `ready`.\n\n'
            'The CSV includes one row per completed response, one column per field (in survey order), '
            'with sensitive field values decrypted.'
        ),
        tags=['Analytics & Exports'],
        request=None,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Export task queued — poll /analytics/reports/ for completion',
                examples=[
                    OpenApiExample(
                        'Export queued',
                        value={
                            'message': 'Export task queued.',
                            'status': 200,
                            'export_report_id': 'f9e8d7c6-0000-0000-0000-000000000001',
                        },
                    )
                ],
            ),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Analyst or Admin role required'),
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Survey not found',
                examples=[OpenApiExample('Not found', value={'message': 'Survey not found.', 'status': 404})],
            ),
        },
    )
)

survey_export_list_schema = extend_schema_view(
    get=extend_schema(
        summary='List export reports for a survey',
        description=(
            'Returns all CSV export reports for this survey ordered newest first.\n\n'
            '**Status values:**\n'
            '- `pending` — task is queued or running\n'
            '- `ready` — CSV file is available at `file_url`\n'
            '- `failed` — task failed after all retries\n\n'
            'Poll this endpoint after triggering an export to check for completion.'
        ),
        tags=['Analytics & Exports'],
        parameters=[
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Filter by export status. Values: `pending`, `ready`, `failed`.',
            ),
            OpenApiParameter(
                name='requested_by__email',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Filter by the email address of the user who triggered the export. Example: `analyst@example.com`',
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Paginated list of export reports',
                examples=[
                    OpenApiExample(
                        'Export reports list',
                        value={
                            'status': 200,
                            'next': None,
                            'previous': None,
                            'total_number_of_objects': 2,
                            'number_of_pages': 1,
                            'current_page': 1,
                            'last_page': 1,
                            'count_items_in_page': 2,
                            'results': [
                                {
                                    'id': 'f9e8d7c6-0000-0000-0000-000000000001',
                                    'status': 'ready',
                                    'requested_by': 'a0b1c2d3-0000-0000-0000-000000000001',
                                    'file_url': 'http://localhost:8000/media/exports/b1c2d3e4/20260518_100000.csv',
                                    'created_at': '2026-05-18T10:00:00Z',
                                },
                                {
                                    'id': 'a1b2c3d4-0000-0000-0000-000000000002',
                                    'status': 'pending',
                                    'requested_by': 'a0b1c2d3-0000-0000-0000-000000000001',
                                    'file_url': '',
                                    'created_at': '2026-05-18T09:30:00Z',
                                },
                            ],
                        },
                    )
                ],
            ),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Analyst or Admin role required'),
            404: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description='Survey not found',
                examples=[OpenApiExample('Not found', value={'message': 'Survey not found.', 'status': 404})],
            ),
        },
    )
)
