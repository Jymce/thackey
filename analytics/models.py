from django.contrib.auth.models import User
from django.db import models


class WeaknessProfile(models.Model):
    """
    Rolling profile of what a user struggles with.

    char_scores:    {"a": {"err": 0.03, "ms": 142.0, "n": 420, "score": 0.21}, ...}
    bigram_scores:  {"th": {"err": 0.01, "ms": 96.0, "n": 85, "score": 0.18}, ...}
    categories:     {"left_hand": 0.4, "pinky": 0.6, "punctuation": 0.7, ...}
    top_weaknesses: [{"type": "bigram", "key": "th", "score": 0.55}, ...]  ranked
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="weakness_profile"
    )
    char_scores = models.JSONField(default=dict)
    bigram_scores = models.JSONField(default=dict)
    categories = models.JSONField(default=dict)
    top_weaknesses = models.JSONField(default=list)
    sessions_analyzed = models.IntegerField(default=0)
    report_text = models.TextField(blank=True)
    report_generated_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"weakness:{self.user.username}"
