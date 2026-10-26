from django.db import models


class TextCorpus(models.Model):
    CATEGORY_CHOICES = [
        ("quote", "Quote"),
        ("common", "Common words"),
        ("code", "Code"),
        ("numbers", "Numbers"),
    ]

    body = models.TextField()
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default="quote")
    difficulty = models.IntegerField(default=1)  # 1 easy — 5 hard
    word_count = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.word_count:
            self.word_count = len(self.body.split())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.category}:{self.body[:40]}..."
