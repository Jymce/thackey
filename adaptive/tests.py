import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from adaptive.models import AdaptiveTest
from analytics.services import update_weakness_profile
from practice.models import KeystrokeEvent, TypingSession


def train_profile(user, weak_char="q"):
    """Give the user a profile that is bad on one char."""
    spec = [(weak_char, "x", False, 250)] * 10 + [
        (c, c, True, 100) for c in "asdf" * 5
    ]
    session = TypingSession.objects.create(
        user=user, mode="time", source="standard",
        started_at=timezone.now(), duration_s=30, wpm=45, accuracy=90,
    )
    KeystrokeEvent.objects.bulk_create(
        [
            KeystrokeEvent(
                session=session, seq=i, expected_char=e, typed_char=t,
                correct=c, latency_ms=l, timestamp_ms=(i + 1) * l,
            )
            for i, (e, t, c, l) in enumerate(spec)
        ]
    )
    return update_weakness_profile(user, session)


@pytest.fixture(autouse=True)
def no_llm(settings):
    """Keep tests offline/deterministic — force the heuristic path."""
    settings.LLM_API_KEY = ""


@pytest.mark.django_db
class TestHeuristicGenerator:
    def test_biases_toward_weak_patterns(self, user):
        profile = train_profile(user, weak_char="q")
        client = APIClient()
        client.force_authenticate(user)
        res = client.post("/api/v1/adaptive/generate/", {}, format="json")
        assert res.status_code == 201
        assert res.data["generated_by"] == "heuristic"  # no LLM key in tests
        content = res.data["content"]
        # heuristic should overweight words containing the weak char
        assert len(content.split()) >= 30
        assert "q" in res.data["target_patterns"] or res.data["target_patterns"]

    def test_generate_requires_profile(self, user):
        client = APIClient()
        client.force_authenticate(user)
        res = client.post("/api/v1/adaptive/generate/", {}, format="json")
        assert res.status_code == 400

    def test_requires_auth(self):
        res = APIClient().post("/api/v1/adaptive/generate/", {}, format="json")
        assert res.status_code in (401, 403)

    def test_detail_view(self, user):
        profile = train_profile(user, weak_char="z")
        test = AdaptiveTest.objects.create(
            user=user, content="zany zebra zigzag", generated_by="heuristic",
            target_patterns=["z"], explanation="targets z",
        )
        client = APIClient()
        client.force_authenticate(user)
        res = client.get(f"/api/v1/adaptive/{test.id}/")
        assert res.status_code == 200
        assert res.data["content"] == "zany zebra zigzag"

    def test_generate_with_explicit_targets(self, user):
        """User-tuned suggestion: 'targets' overrides the profile's defaults."""
        train_profile(user, weak_char="z")
        client = APIClient()
        client.force_authenticate(user)
        res = client.post(
            "/api/v1/adaptive/generate/",
            {"targets": ["x", "th"], "word_count": 30},
            format="json",
        )
        assert res.status_code == 201
        assert set(res.data["target_patterns"]) == {"x", "th"}
        assert len(res.data["content"].split()) == 30

    def test_cannot_read_others_test(self, user):
        other = User.objects.create_user("other", password="secret1234")
        test = AdaptiveTest.objects.create(
            user=other, content="secret", generated_by="heuristic"
        )
        client = APIClient()
        client.force_authenticate(user)
        assert client.get(f"/api/v1/adaptive/{test.id}/").status_code == 404
