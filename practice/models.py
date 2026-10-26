from django.contrib.auth.models import User
from django.db import models


class TypingSession(models.Model):
    MODE_CHOICES = [
        ("time", "Time"),
        ("words", "Words"),
        ("quote", "Quote"),
        ("adaptive", "Adaptive"),
    ]
    SOURCE_CHOICES = [
        ("standard", "Standard"),
        ("adaptive", "Adaptive"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="typing_sessions")
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default="time")
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="standard")
    adaptive_test = models.ForeignKey(
        "adaptive.AdaptiveTest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
    )
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_s = models.FloatField()
    wpm = models.FloatField()
    raw_wpm = models.FloatField(default=0)
    accuracy = models.FloatField()
    consistency = models.FloatField(null=True, blank=True)
    char_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        return f"{self.user.username} {self.wpm}wpm {self.accuracy}%"


class KeystrokeEvent(models.Model):
    """One key press inside a session. The raw material for weakness analysis."""

    session = models.ForeignKey(
        TypingSession, on_delete=models.CASCADE, related_name="keystrokes"
    )
    seq = models.IntegerField()
    expected_char = models.CharField(max_length=4, blank=True)
    typed_char = models.CharField(max_length=4, blank=True)
    correct = models.BooleanField(default=True)
    latency_ms = models.FloatField(null=True, blank=True)  # ms since previous keystroke
    timestamp_ms = models.FloatField(default=0)  # ms since session start
    is_backspace = models.BooleanField(default=False)

    class Meta:
        ordering = ["seq"]
        indexes = [models.Index(fields=["session", "seq"])]

    def __str__(self):
        return f"{self.session_id}:{self.seq}"
