from django.contrib.auth.models import User
from django.db import models


class AdaptiveTest(models.Model):
    GENERATOR_CHOICES = [
        ("heuristic", "Heuristic"),
        ("llm", "LLM"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="adaptive_tests"
    )
    content = models.TextField()
    generated_by = models.CharField(max_length=10, choices=GENERATOR_CHOICES)
    target_patterns = models.JSONField(default=list)
    explanation = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"adaptive:{self.user.username}:{self.id}"
