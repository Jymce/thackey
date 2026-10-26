from django.contrib.auth.models import User
from rest_framework import serializers

from accounts.models import UserSettings


class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = ["theme", "keyboard_layout", "default_mode", "default_duration"]


class UserSerializer(serializers.ModelSerializer):
    settings = UserSettingsSerializer()

    class Meta:
        model = User
        fields = ["id", "username", "email", "date_joined", "settings"]
        read_only_fields = ["id", "date_joined"]

    def update(self, instance, validated_data):
        settings_data = validated_data.pop("settings", None)
        instance.email = validated_data.get("email", instance.email)
        instance.save()
        if settings_data is not None:
            settings_serializer = UserSettingsSerializer(
                instance.settings, data=settings_data, partial=True
            )
            settings_serializer.is_valid(raise_exception=True)
            settings_serializer.save()
        return instance


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
