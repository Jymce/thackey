from django.contrib import admin

from accounts.models import UserSettings


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ["user", "theme", "keyboard_layout", "default_mode"]
