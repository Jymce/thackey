import pytest
from rest_framework.test import APIClient

from texts.models import TextCorpus


@pytest.mark.django_db
class TestTextsAPI:
    def test_random_words_anonymous(self):
        res = APIClient().get("/api/v1/texts/random/?category=words&count=25")
        assert res.status_code == 200
        assert len(res.data["content"].split()) == 25

    def test_random_quote(self):
        TextCorpus.objects.create(body="Stay hungry, stay foolish.", category="quote")
        res = APIClient().get("/api/v1/texts/random/?category=quote")
        assert res.status_code == 200
        assert res.data["body"] == "Stay hungry, stay foolish."

    def test_fallback_to_words_when_corpus_empty(self):
        res = APIClient().get("/api/v1/texts/random/?category=quote")
        assert res.status_code == 200
        assert res.data["content"]
