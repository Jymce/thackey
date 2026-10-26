from rest_framework import serializers

from texts.models import TextCorpus


class TextCorpusSerializer(serializers.ModelSerializer):
    class Meta:
        model = TextCorpus
        fields = ["id", "body", "category", "difficulty", "word_count"]
