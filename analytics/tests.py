import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from analytics.models import WeaknessProfile
from analytics.services import (
    compute_strengths,
    extract_features,
    suggest_practice,
    update_weakness_profile,
)
from practice.models import KeystrokeEvent, TypingSession


def make_session(user, events_spec):
    """events_spec: list of (expected, typed, correct, latency_ms)."""
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
            for i, (e, t, c, l) in enumerate(events_spec)
        ]
    )
    return session


@pytest.mark.django_db
class TestFeatureExtraction:
    def test_extract_chars_and_bigrams(self, user):
        events = [
            ("t", "t", True, 100), ("h", "h", True, 90), ("e", "x", False, 150),
        ]
        session = make_session(user, events)
        chars, bigrams, backspaces = extract_features(
            session.keystrokes.order_by("seq")
        )
        assert chars["e"] == [1, 1, 150.0]
        assert "th" in bigrams and "he" in bigrams
        assert backspaces == 0

    def test_profile_flags_error_prone_char(self, user):
        # 'q' always mistyped, everything else fine
        spec = [(c, c, True, 100) for c in "abcdefghij" * 5]
        spec += [("q", "w", False, 100)] * 10
        session = make_session(user, spec)
        profile = update_weakness_profile(user, session)

        assert profile.char_scores["q"]["err"] == 1.0
        assert profile.char_scores["q"]["score"] > 0.5
        weak_keys = [w["key"] for w in profile.top_weaknesses]
        assert "q" in weak_keys

    def test_profile_flags_slow_char(self, user):
        spec = [(c, c, True, 100) for c in "abcdefghij" * 5]
        spec += [("z", "z", True, 400)] * 10  # z is 4x slower
        session = make_session(user, spec)
        profile = update_weakness_profile(user, session)

        assert profile.char_scores["z"]["ms"] == 400.0
        assert profile.char_scores["z"]["score"] > 0
        weak_keys = [w["key"] for w in profile.top_weaknesses]
        assert "z" in weak_keys

    def test_recency_weighting(self, user):
        # Session 1: bad on 'q'. Session 2: perfect on 'q'.
        s1 = make_session(user, [("q", "w", False, 200)] * 8 + [(c, c, True, 100) for c in "abcde" * 4])
        update_weakness_profile(user, s1)
        p1 = WeaknessProfile.objects.get(user=user)
        q_err_after_bad = p1.char_scores["q"]["err"]

        s2 = make_session(user, [("q", "q", True, 100)] * 8 + [(c, c, True, 100) for c in "abcde" * 4])
        update_weakness_profile(user, s2)
        p2 = WeaknessProfile.objects.get(user=user)

        # Decay: 'q' error rate should have dropped after a clean session
        assert p2.char_scores["q"]["err"] < q_err_after_bad
        assert p2.sessions_analyzed == 2

    def test_categories_detected(self, user):
        spec = [("p", "o", False, 150)] * 10 + [(c, c, True, 100) for c in "asdf" * 5]
        session = make_session(user, spec)
        profile = update_weakness_profile(user, session)
        # 'p' is a right-pinky key
        assert "pinky" in profile.categories or "right_hand" in profile.categories


@pytest.mark.django_db
class TestAnalyticsAPI:
    def test_profile_endpoint(self, user):
        client = APIClient()
        client.force_authenticate(user)
        assert client.get("/api/v1/analytics/profile/").data["profile"] is None

        spec = [("q", "w", False, 100)] * 10 + [(c, c, True, 100) for c in "asdf" * 5]
        update_weakness_profile(user, make_session(user, spec))

        res = client.get("/api/v1/analytics/profile/")
        assert res.data["profile"]["sessions_analyzed"] == 1

    def test_trends_endpoint(self, user):
        client = APIClient()
        client.force_authenticate(user)
        make_session(user, [("a", "a", True, 100)])
        res = client.get("/api/v1/analytics/trends/")
        assert res.status_code == 200
        assert len(res.data["sessions"]) == 1

    def test_report_fallback_without_llm(self, user, settings):
        settings.LLM_API_KEY = ""
        client = APIClient()
        client.force_authenticate(user)
        spec = [("q", "w", False, 100)] * 10 + [(c, c, True, 100) for c in "asdf" * 5]
        update_weakness_profile(user, make_session(user, spec))
        res = client.get("/api/v1/analytics/report/")
        assert res.status_code == 200
        assert "q" in res.data["report"]

    def test_report_includes_strengths_and_suggestion(self, user, settings):
        settings.LLM_API_KEY = ""
        client = APIClient()
        client.force_authenticate(user)
        # 'a','s','d','f' clean & fast; 'q' bad
        spec = [("q", "w", False, 200)] * 10 + [(c, c, True, 90) for c in "asdf" * 8]
        update_weakness_profile(user, make_session(user, spec))
        res = client.get("/api/v1/analytics/report/")
        assert res.status_code == 200
        strong_keys = [s["key"] for s in res.data["profile"]["strengths"]]
        assert "a" in strong_keys
        assert "q" not in strong_keys
        assert "q" in res.data["suggestion"]["targets"]
        assert res.data["suggestion"]["word_count"] in (50, 75)


@pytest.mark.django_db
class TestSuggestion:
    def test_suggest_practice_uses_top_weaknesses(self, user):
        spec = [("z", "x", False, 300)] * 10 + [(c, c, True, 100) for c in "asdf" * 8]
        profile = update_weakness_profile(user, make_session(user, spec))
        s = suggest_practice(profile)
        assert "z" in s["targets"]
        assert s["rationale"]
        assert s["word_count"] in (50, 75)

    def test_compute_strengths_needs_samples(self, user):
        # 2 clean samples for 'w' — below MIN_CHAR_SAMPLES, not a strength
        spec = [("w", "w", True, 80)] * 2 + [("q", "w", False, 200)] * 10
        profile = update_weakness_profile(user, make_session(user, spec))
        keys = [s["key"] for s in compute_strengths(profile)]
        assert "w" not in keys  # insufficient samples
        assert "q" not in keys  # weak, not strong
