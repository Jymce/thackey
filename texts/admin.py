from django.contrib import admin

from texts.models import TextCorpus


@admin.register(TextCorpus)
class TextCorpusAdmin(admin.ModelAdmin):
    list_display = ["category", "difficulty", "word_count"]
    list_filter = ["category", "difficulty"]
