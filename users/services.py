"""
Service layer for the Users domain.

Provides UserService to encapsulate user registration and authentication
logic independently from views and serializers.
"""
import logging

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from .models import User

logger = logging.getLogger("users")


class UserService:
    """Encapsulates all user registration / authentication business logic."""

    @staticmethod
    def register(*, username, email, password, first_name="", last_name="", phone_number=""):
        """
        Create a new user.

        Raises django.core.exceptions.ValidationError on any validation
        failure (duplicate email, weak password, etc.) so callers (both
        the API view and the web view) can render a single consistent
        error message.
        """
        email = email.strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError({"email": "A user with this email already exists."})

        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError({"username": "This username is already taken."})

        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
        )
        validate_password(password, user=user)
        user.set_password(password)

        try:
            user.full_clean(exclude=["password"])
            user.save()
        except IntegrityError as exc:
            logger.warning("Registration integrity error for %s: %s", email, exc)
            raise ValidationError("Could not create user due to a conflicting record.")

        logger.info("New user registered: %s (%s)", user.username, user.email)
        return user

    @staticmethod
    def authenticate(*, username_or_email, password, request=None):
        """
        Authenticate by username OR email + password.
        Returns the authenticated User, or None.
        """
        user = authenticate(request=request, username=username_or_email, password=password)
        if user is None:
            try:
                candidate = User.objects.get(email__iexact=username_or_email)
                user = authenticate(request=request, username=candidate.username, password=password)
            except User.DoesNotExist:
                user = None

        if user:
            logger.info("User authenticated: %s", user.username)
        else:
            logger.info("Failed authentication attempt for: %s", username_or_email)
        return user
