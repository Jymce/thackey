from django.contrib import admin

from practice.models import KeystrokeEvent, TypingSession


class KeystrokeInline(admin.TabularInline):
    model = KeystrokeEvent
    extra = 0
    can_delete = False


@admin.register(TypingSession)
class TypingSessionAdmin(admin.ModelAdmin):
    list_display = ["user", "mode", "source", "wpm", "accuracy", "created_at"]
    list_filter = ["mode", "source"]
    inlines = [KeystrokeInline]
