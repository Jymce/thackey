import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from analytics.models import WeaknessProfile
from practice.models import KeystrokeEvent, TypingSession


@pytest.fixture
def user():
    return User.objects.create_user("typer", password="secret1234")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def make_keystrokes(text, bad_chars=frozenset(), latency=120.0):
    events = []
    ts = 0.0
    for i, ch in enumerate(text):
        ts += latency
        events.append(
            {
                "seq": i,
                "expected_char": ch,
                "typed_char": "_" if ch in bad_chars else ch,
                "correct": ch not in bad_chars,
                "latency_ms": latency,
                "timestamp_ms": ts,
                "is_backspace": False,
            }
        )
    return events


def make_session_payload(text, keystrokes):
    return {
        "mode": "time",
        "source": "standard",
        "started_at": timezone.now().isoformat(),
        "duration_s": 30.0,
        "wpm": 50.0,
        "raw_wpm": 55.0,
        "accuracy": 95.0,
        "char_count": len(text),
        "error_count": len(text) // 20,
        "keystrokes": keystrokes,
    }


@pytest.mark.django_db
class TestSessionIngest:
    def test_create_session_with_keystrokes(self, client, user):
        text = "the quick brown fox jumps"
        payload = make_session_payload(text, make_keystrokes(text))
        res = client.post("/api/v1/sessions/", payload, format="json")
        assert res.status_code == 201
        session = TypingSession.objects.get(id=res.data["id"])
        assert session.user == user
        assert KeystrokeEvent.objects.filter(session=session).count() == len(text)

    def test_session_with_backspaces_accepted(self, client, user):
        """Regression: backspace events (empty expected_char) used to 400 the whole POST."""
        text = "abc"
        ks = make_keystrokes(text) + [
            {"seq": 3, "expected_char": "", "typed_char": "", "correct": False,
             "latency_ms": 90, "timestamp_ms": 400, "is_backspace": True},
        ]
        res = client.post("/api/v1/sessions/", make_session_payload("abcx", ks), format="json")
        assert res.status_code == 201, res.data
        session = TypingSession.objects.get(id=res.data["id"])
        assert session.keystrokes.filter(is_backspace=True).count() == 1

    def test_response_includes_analysis(self, client, user):
        """POST response should carry hotspots + profile for the result modal."""
        text = "qqqaaazzz"
        res = client.post(
            "/api/v1/sessions/",
            make_session_payload(text, make_keystrokes(text, bad_chars={"q"})),
            format="json",
        )
        assert res.status_code == 201
        analysis = res.data["analysis"]
        hot_keys = [h["key"] for h in analysis["hotspots"]]
        assert "q" in hot_keys
        assert "suggestion" in analysis
        assert "top_weaknesses" in analysis

    def test_session_updates_weakness_profile(self, client, user):
        text = "qqqaaazzz"
        payload = make_session_payload(text, make_keystrokes(text, bad_chars={"q"}))
        res = client.post("/api/v1/sessions/", payload, format="json")
        assert res.status_code == 201
        profile = WeaknessProfile.objects.get(user=user)
        assert profile.sessions_analyzed == 1
        assert profile.char_scores["q"]["err"] == 1.0

    def test_list_only_own_sessions(self, client, user):
        other = User.objects.create_user("other", password="secret1234")
        TypingSession.objects.create(
            user=other, mode="time", source="standard",
            started_at=timezone.now(), duration_s=30, wpm=40, accuracy=90,
        )
        text = "abc"
        client.post(
            "/api/v1/sessions/",
            make_session_payload(text, make_keystrokes(text)),
            format="json",
        )
        res = client.get("/api/v1/sessions/")
        assert res.status_code == 200
        assert res.data["count"] == 1

    def test_requires_auth(self):
        # SessionAuthentication yields no WWW-Authenticate challenge -> 403
        res = APIClient().get("/api/v1/sessions/")
        assert res.status_code in (401, 403)
