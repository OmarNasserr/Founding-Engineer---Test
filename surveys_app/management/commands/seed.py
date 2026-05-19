import json
import random
from django.core.management.base import BaseCommand
from django.utils import timezone

# Fixed UUIDs so the Postman collection works out of the box without
# needing to copy IDs from responses after each fresh setup.
SURVEY_ID   = '10000000-0000-0000-0000-000000000001'
SECTION_1_ID = '20000000-0000-0000-0000-000000000001'
SECTION_2_ID = '20000000-0000-0000-0000-000000000002'
SECTION_3_ID = '20000000-0000-0000-0000-000000000003'
FIELD_FULL_NAME_ID   = '30000000-0000-0000-0000-000000000001'
FIELD_EMAIL_ID       = '30000000-0000-0000-0000-000000000002'
FIELD_OWNS_CAR_ID    = '30000000-0000-0000-0000-000000000003'
FIELD_CAR_BRAND_ID   = '30000000-0000-0000-0000-000000000004'
FIELD_YEAR_ID        = '30000000-0000-0000-0000-000000000005'
FIELD_COMMENTS_ID    = '30000000-0000-0000-0000-000000000006'
FIELD_RATING_ID      = '30000000-0000-0000-0000-000000000007'


class Command(BaseCommand):
    help = 'Seed the database with sample data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding database...')
        self._create_users()
        survey = self._create_survey()
        self._create_responses(survey)
        self.stdout.write(self.style.SUCCESS('Seeding complete.'))

    def _create_users(self):
        from accounts_app.models import User
        users = [
            ('admin@survey.com',   'admin',    'Admin1234!',   'admin'),
            ('analyst@survey.com', 'analyst',  'Admin1234!',   'analyst'),
            ('viewer@survey.com',  'viewer',   'Admin1234!',   'data_viewer'),
        ]
        for email, username, password, role in users:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={'username': username, 'role': role},
            )
            if created:
                user.set_password(password)
                user.save()
                self.stdout.write(f'  Created user: {email}')
            else:
                self.stdout.write(f'  User exists: {email}')

    def _create_survey(self):
        from accounts_app.models import User
        from surveys_app.models import Survey, Section, Field, SurveyStatus, FieldType, MapsTo

        admin = User.objects.get(email='admin@survey.com')

        survey, created = Survey.objects.get_or_create(
            id=SURVEY_ID,
            defaults={
                'title': 'Customer Satisfaction Survey',
                'description': 'A sample survey with conditional logic.',
                'status': SurveyStatus.PUBLISHED,
                'created_by': admin,
            },
        )
        if not created:
            self.stdout.write('  Survey already exists, skipping sections/fields.')
            return survey

        # Section 1 — Personal Info (no conditions)
        s1, _ = Section.objects.get_or_create(
            id=SECTION_1_ID,
            defaults={'survey': survey, 'title': 'Personal Info', 'order': 1, 'conditions': None},
        )
        Field.objects.get_or_create(id=FIELD_FULL_NAME_ID, defaults={
            'section': s1, 'label': 'Full Name', 'field_type': FieldType.TEXT,
            'order': 1, 'is_required': True, 'maps_to': MapsTo.RESPONDENT_FULL_NAME,
        })
        Field.objects.get_or_create(id=FIELD_EMAIL_ID, defaults={
            'section': s1, 'label': 'Email Address', 'field_type': FieldType.EMAIL,
            'order': 2, 'is_required': True, 'maps_to': MapsTo.RESPONDENT_EMAIL,
        })
        Field.objects.get_or_create(id=FIELD_OWNS_CAR_ID, defaults={
            'section': s1, 'label': 'Do you own a car?', 'field_type': FieldType.RADIO,
            'order': 3, 'is_required': True, 'options': ['Yes', 'No'],
        })

        # Section 2 — Vehicle Details (conditional on owns_car == Yes)
        s2, _ = Section.objects.get_or_create(
            id=SECTION_2_ID,
            defaults={
                'survey': survey,
                'title': 'Vehicle Details',
                'order': 2,
                'conditions': {
                    'conditions': [
                        {'field_id': FIELD_OWNS_CAR_ID, 'operator': 'eq', 'value': 'Yes'}
                    ]
                },
            },
        )
        Field.objects.get_or_create(id=FIELD_CAR_BRAND_ID, defaults={
            'section': s2, 'label': 'Car Brand', 'field_type': FieldType.DROPDOWN,
            'order': 1, 'is_required': True,
            'options': ['Toyota', 'Honda', 'Ford', 'BMW', 'Tesla', 'Other'],
        })
        Field.objects.get_or_create(id=FIELD_YEAR_ID, defaults={
            'section': s2, 'label': 'Year of Manufacture', 'field_type': FieldType.NUMBER,
            'order': 2, 'is_required': True, 'validation_rules': {'min': 1900, 'max': 2025},
        })

        # Section 3 — General Feedback (no conditions)
        s3, _ = Section.objects.get_or_create(
            id=SECTION_3_ID,
            defaults={'survey': survey, 'title': 'General Feedback', 'order': 3, 'conditions': None},
        )
        Field.objects.get_or_create(id=FIELD_COMMENTS_ID, defaults={
            'section': s3, 'label': 'Additional Comments', 'field_type': FieldType.TEXTAREA,
            'order': 1, 'is_required': False,
        })
        Field.objects.get_or_create(id=FIELD_RATING_ID, defaults={
            'section': s3, 'label': 'Overall Satisfaction (1-5)', 'field_type': FieldType.RATING,
            'order': 2, 'is_required': True, 'validation_rules': {'min': 1, 'max': 5},
        })

        self.stdout.write(f'  Created survey: {survey.title} (id: {SURVEY_ID})')
        return survey

    def _create_responses(self, survey):
        from surveys_app.models import (
            Respondent, SurveyResponse, FieldResponse,
            SurveyResponseStatus, Field,
        )

        def get_field(field_id):
            return Field.objects.filter(id=field_id).first()

        name_field    = get_field(FIELD_FULL_NAME_ID)
        email_field   = get_field(FIELD_EMAIL_ID)
        car_field     = get_field(FIELD_OWNS_CAR_ID)
        brand_field   = get_field(FIELD_CAR_BRAND_ID)
        year_field    = get_field(FIELD_YEAR_ID)
        comment_field = get_field(FIELD_COMMENTS_ID)
        rating_field  = get_field(FIELD_RATING_ID)

        car_owners = [
            ('Alice Johnson', 'alice@example.com', 'Yes', 'Toyota', '2020', 'Great service!', '5'),
            ('Bob Smith',     'bob@example.com',   'Yes', 'Honda',  '2018', 'Pretty good.',   '4'),
            ('Carol White',   'carol@example.com', 'Yes', 'Tesla',  '2022', 'Excellent!',     '5'),
            ('David Brown',   'david@example.com', 'Yes', 'BMW',    '2019', 'Very satisfied.','4'),
            ('Eva Martinez',  'eva@example.com',   'Yes', 'Ford',   '2015', 'Decent.',        '3'),
        ]
        non_car_owners = [
            ('Frank Lee',    'frank@example.com', 'No', 'Good overall.',     '4'),
            ('Grace Kim',    'grace@example.com', 'No', 'Loved it!',         '5'),
            ('Henry Chen',   'henry@example.com', 'No', 'Could be better.',  '3'),
            ('Iris Patel',   'iris@example.com',  'No', 'Satisfactory.',     '4'),
            ('Jack Wilson',  'jack@example.com',  'No', 'Not bad.',          '3'),
        ]

        count = 0
        for data in car_owners:
            name, email, has_car, brand, year, comment, rating = data
            respondent, _ = Respondent.objects.get_or_create(email=email, defaults={'full_name': name})
            sr, created = SurveyResponse.objects.get_or_create(
                survey=survey, respondent=respondent,
                defaults={'status': SurveyResponseStatus.COMPLETED, 'submitted_at': timezone.now()},
            )
            if created:
                for field, value in [
                    (name_field, name), (email_field, email), (car_field, has_car),
                    (brand_field, brand), (year_field, year),
                    (comment_field, comment), (rating_field, rating),
                ]:
                    if field:
                        FieldResponse.objects.get_or_create(
                            survey_response=sr, field=field, defaults={'value': value}
                        )
                count += 1

        for data in non_car_owners:
            name, email, has_car, comment, rating = data
            respondent, _ = Respondent.objects.get_or_create(email=email, defaults={'full_name': name})
            sr, created = SurveyResponse.objects.get_or_create(
                survey=survey, respondent=respondent,
                defaults={'status': SurveyResponseStatus.COMPLETED, 'submitted_at': timezone.now()},
            )
            if created:
                for field, value in [
                    (name_field, name), (email_field, email), (car_field, has_car),
                    (comment_field, comment), (rating_field, rating),
                ]:
                    if field:
                        FieldResponse.objects.get_or_create(
                            survey_response=sr, field=field, defaults={'value': value}
                        )
                count += 1

        self.stdout.write(f'  Created {count} sample responses.')
