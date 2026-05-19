from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserRole(models.TextChoices):
    ADMIN = 'admin', _('Admin')
    ANALYST = 'analyst', _('Analyst')
    DATA_VIEWER = 'data_viewer', _('Data Viewer')


class User(AbstractUser):
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.DATA_VIEWER, db_index=True)

    def __str__(self):
        return self.username
