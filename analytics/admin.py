from django.contrib import admin

from analytics.models import WeaknessProfile


@admin.register(WeaknessProfile)
class WeaknessProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "sessions_analyzed", "updated_at"]
    readonly_fields = ["char_scores", "bigram_scores", "categories", "top_weaknesses"]
