from django.contrib import admin

from adaptive.models import AdaptiveTest


@admin.register(AdaptiveTest)
class AdaptiveTestAdmin(admin.ModelAdmin):
    list_display = ["user", "generated_by", "created_at"]
    list_filter = ["generated_by"]
