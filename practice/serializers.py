from rest_framework import serializers

from practice.models import KeystrokeEvent, TypingSession

MAX_KEYSTROKES_PER_SESSION = 20_000


class KeystrokeEventSerializer(serializers.ModelSerializer):
    # Spaces are legitimate typed chars — don't let DRF trim them to "".
    # Backspace events carry no expected char at all -> allow blank too.
    expected_char = serializers.CharField(
        max_length=4, allow_blank=True, trim_whitespace=False
    )
    typed_char = serializers.CharField(
        max_length=4, allow_blank=True, trim_whitespace=False
    )

    class Meta:
        model = KeystrokeEvent
        fields = [
            "seq",
            "expected_char",
            "typed_char",
            "correct",
            "latency_ms",
            "timestamp_ms",
            "is_backspace",
        ]


class TypingSessionSerializer(serializers.ModelSerializer):
    keystroke_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = TypingSession
        fields = [
            "id",
            "mode",
            "source",
            "adaptive_test",
            "started_at",
            "finished_at",
            "duration_s",
            "wpm",
            "raw_wpm",
            "accuracy",
            "consistency",
            "char_count",
            "error_count",
            "created_at",
            "keystroke_count",
        ]
        read_only_fields = ["id", "created_at"]


class TypingSessionDetailSerializer(TypingSessionSerializer):
    keystrokes = KeystrokeEventSerializer(many=True, read_only=True)

    class Meta(TypingSessionSerializer.Meta):
        fields = TypingSessionSerializer.Meta.fields + ["keystrokes"]


class TypingSessionCreateSerializer(serializers.ModelSerializer):
    keystrokes = KeystrokeEventSerializer(many=True, required=False)

    class Meta:
        model = TypingSession
        fields = [
            "mode",
            "source",
            "adaptive_test",
            "started_at",
            "finished_at",
            "duration_s",
            "wpm",
            "raw_wpm",
            "accuracy",
            "consistency",
            "char_count",
            "error_count",
            "keystrokes",
        ]

    def validate_keystrokes(self, value):
        if len(value) > MAX_KEYSTROKES_PER_SESSION:
            raise serializers.ValidationError("Too many keystroke events.")
        return value

    def validate(self, attrs):
        if attrs["duration_s"] <= 0:
            raise serializers.ValidationError({"duration_s": "Must be positive."})
        if not 0 <= attrs["accuracy"] <= 100:
            raise serializers.ValidationError({"accuracy": "Must be 0-100."})
        return attrs

    def create(self, validated_data):
        keystrokes = validated_data.pop("keystrokes", [])
        session = TypingSession.objects.create(**validated_data)
        KeystrokeEvent.objects.bulk_create(
            [KeystrokeEvent(session=session, **k) for k in keystrokes]
        )
        return session
