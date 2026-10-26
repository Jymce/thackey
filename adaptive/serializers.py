from rest_framework import serializers

from adaptive.models import AdaptiveTest


class AdaptiveTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdaptiveTest
        fields = [
            "id",
            "content",
            "generated_by",
            "target_patterns",
            "explanation",
            "created_at",
        ]
