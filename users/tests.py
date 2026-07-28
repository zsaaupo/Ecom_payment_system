from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import User
from .services import UserService


class UserModelTests(TestCase):
    def test_email_must_be_unique(self):
        User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        with self.assertRaises(Exception):
            u2 = User(username="alice2", email="alice@example.com")
            u2.set_password("pass12345")
            u2.full_clean()


class UserServiceTests(TestCase):
    def test_register_via_service(self):
        user = UserService.register(username="bob", email="bob@example.com", password="StrongPass123!")
        self.assertTrue(user.check_password("StrongPass123!"))
        self.assertEqual(user.email, "bob@example.com")

    def test_register_duplicate_email_rejected(self):
        UserService.register(username="carol", email="carol@example.com", password="StrongPass123!")
        with self.assertRaises(ValidationError):
            UserService.register(username="carol2", email="carol@example.com", password="StrongPass123!")

    def test_authenticate_by_email(self):
        UserService.register(username="dave", email="dave@example.com", password="StrongPass123!")
        user = UserService.authenticate(username_or_email="dave@example.com", password="StrongPass123!")
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "dave")

    def test_authenticate_wrong_password_returns_none(self):
        UserService.register(username="erin", email="erin@example.com", password="StrongPass123!")
        user = UserService.authenticate(username_or_email="erin", password="WrongPassword!")
        self.assertIsNone(user)
