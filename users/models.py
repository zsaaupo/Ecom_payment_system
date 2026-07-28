from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model.

    Requirement (2.1.1 User Management): "Email must be unique."
    Django's default AbstractUser leaves email non-unique, so we override it.
    """
    email = models.EmailField("email address", unique=True, db_index=True)
    phone_number = models.CharField(max_length=20, blank=True)
    is_customer_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    REQUIRED_FIELDS = ["email"]

    class Meta:
        indexes = [
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return self.username

    @property
    def is_admin_user(self):
        return self.is_staff or self.is_superuser
