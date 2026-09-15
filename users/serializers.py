from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.exclude(pk=self.instance.pk).filter(email__iexact=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate_username(self, value):
        if User.objects.exclude(pk=self.instance.pk).filter(username__iexact=value).exists():
            raise serializers.ValidationError('This username is already taken.')
        return value

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "phone_number", "is_staff", "date_joined"]
        read_only_fields = ["id", "is_staff", "date_joined"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False, validators=[validate_password])

    class Meta:
        model = User
        fields = ["username", "email", "password", "first_name", "last_name", "phone_number"]

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(help_text="Username or email")
    password = serializers.CharField(write_only=True, trim_whitespace=False)
