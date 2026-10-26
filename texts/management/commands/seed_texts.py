from django.core.management.base import BaseCommand

from texts.models import TextCorpus
from texts.wordlists import QUOTES


class Command(BaseCommand):
    help = "Seed the TextCorpus table with starter quotes."

    def handle(self, *args, **options):
        created = 0
        for body in QUOTES:
            _, was_created = TextCorpus.objects.get_or_create(
                body=body, defaults={"category": "quote", "difficulty": 1}
            )
            created += int(was_created)
        self.stdout.write(
            self.style.SUCCESS(f"Seeded {created} texts ({len(QUOTES)} total known).")
        )
