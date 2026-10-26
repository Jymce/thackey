from django.contrib.auth.models import User
from django.db import models


class UserSettings(models.Model):
    THEME_CHOICES = [
        ("dark", "Dark"),
        ("light", "Light"),
        ("system", "System"),
    ]
    LAYOUT_CHOICES = [
        ("qwerty", "QWERTY"),
        ("dvorak", "Dvorak"),
        ("colemak", "Colemak"),
    ]
    MODE_CHOICES = [
        ("time", "Time"),
        ("words", "Words"),
        ("adaptive", "Adaptive"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="settings")
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default="system")
    keyboard_layout = models.CharField(max_length=10, choices=LAYOUT_CHOICES, default="qwerty")
    default_mode = models.CharField(max_length=10, choices=MODE_CHOICES, default="time")
    default_duration = models.IntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"settings:{self.user.username}"
