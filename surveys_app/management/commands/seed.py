import json
import random
from django.core.management.base import BaseCommand
from django.utils import timezone


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
            ('admin@survey.com', 'admin', 'Admin1234!', 'admin'),
            ('analyst@survey.com', 'analyst', 'Admin1234!', 'analyst'),
            ('viewer@survey.com', 'viewer', 'Admin1234!', 'data_viewer'),
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
            title='Customer Satisfaction Survey',
            defaults={
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
            survey=survey, order=1,
            defaults={'title': 'Personal Info', 'conditions': None},
        )
        Field.objects.get_or_create(section=s1, order=1, defaults={
            'label': 'Full Name', 'field_type': FieldType.TEXT,
            'is_required': True, 'maps_to': MapsTo.RESPONDENT_FULL_NAME,
        })
        Field.objects.get_or_create(section=s1, order=2, defaults={
            'label': 'Email Address', 'field_type': FieldType.EMAIL,
            'is_required': True, 'maps_to': MapsTo.RESPONDENT_EMAIL,
        })
        owns_car_field, _ = Field.objects.get_or_create(section=s1, order=3, defaults={
            'label': 'Do you own a car?', 'field_type': FieldType.RADIO,
            'is_required': True,
            'options': ['Yes', 'No'],
        })

        # Section 2 — Vehicle Details (conditional on owns_car == Yes)
        s2, _ = Section.objects.get_or_create(
            survey=survey, order=2,
            defaults={
                'title': 'Vehicle Details',
                'conditions': {
                    'conditions': [
                        {'field_id': str(owns_car_field.id), 'operator': 'eq', 'value': 'Yes'}
                    ]
                },
            },
        )
        Field.objects.get_or_create(section=s2, order=1, defaults={
            'label': 'Car Brand', 'field_type': FieldType.DROPDOWN,
            'is_required': True,
            'options': ['Toyota', 'Honda', 'Ford', 'BMW', 'Tesla', 'Other'],
        })
        Field.objects.get_or_create(section=s2, order=2, defaults={
            'label': 'Year of Manufacture', 'field_type': FieldType.NUMBER,
            'is_required': True,
            'validation_rules': {'min': 1900, 'max': 2025},
        })

        # Section 3 — General Feedback (no conditions)
        s3, _ = Section.objects.get_or_create(
            survey=survey, order=3,
            defaults={'title': 'General Feedback', 'conditions': None},
        )
        Field.objects.get_or_create(section=s3, order=1, defaults={
            'label': 'Additional Comments', 'field_type': FieldType.TEXTAREA,
            'is_required': False,
        })
        Field.objects.get_or_create(section=s3, order=2, defaults={
            'label': 'Overall Satisfaction (1-5)', 'field_type': FieldType.RATING,
            'is_required': True,
            'validation_rules': {'min': 1, 'max': 5},
        })

        self.stdout.write(f'  Created survey: {survey.title}')
        return survey

    def _create_responses(self, survey):
        from surveys_app.models import (
            Respondent, SurveyResponse, FieldResponse,
            SurveyResponseStatus, Field
        )

        # Get fields by label for easy lookup
        def get_field(label):
            return Field.objects.filter(section__survey=survey, label=label).first()

        name_field = get_field('Full Name')
        email_field = get_field('Email Address')
        car_field = get_field('Do you own a car?')
        brand_field = get_field('Car Brand')
        year_field = get_field('Year of Manufacture')
        comment_field = get_field('Additional Comments')
        rating_field = get_field('Overall Satisfaction (1-5)')

        car_owners = [
            ('Alice Johnson', 'alice@example.com', 'Yes', 'Toyota', '2020', 'Great service!', '5'),
            ('Bob Smith', 'bob@example.com', 'Yes', 'Honda', '2018', 'Pretty good.', '4'),
            ('Carol White', 'carol@example.com', 'Yes', 'Tesla', '2022', 'Excellent!', '5'),
            ('David Brown', 'david@example.com', 'Yes', 'BMW', '2019', 'Very satisfied.', '4'),
            ('Eva Martinez', 'eva@example.com', 'Yes', 'Ford', '2015', 'Decent experience.', '3'),
        ]
        non_car_owners = [
            ('Frank Lee', 'frank@example.com', 'No', 'Good overall.', '4'),
            ('Grace Kim', 'grace@example.com', 'No', 'Loved it!', '5'),
            ('Henry Chen', 'henry@example.com', 'No', 'Could be better.', '3'),
            ('Iris Patel', 'iris@example.com', 'No', 'Satisfactory.', '4'),
            ('Jack Wilson', 'jack@example.com', 'No', 'Not bad.', '3'),
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
                answers = [
                    (name_field, name), (email_field, email), (car_field, has_car),
                    (brand_field, brand), (year_field, year),
                    (comment_field, comment), (rating_field, rating),
                ]
                for field, value in answers:
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
                answers = [
                    (name_field, name), (email_field, email), (car_field, has_car),
                    (comment_field, comment), (rating_field, rating),
                ]
                for field, value in answers:
                    if field:
                        FieldResponse.objects.get_or_create(
                            survey_response=sr, field=field, defaults={'value': value}
                        )
                count += 1

        self.stdout.write(f'  Created {count} sample responses.')
