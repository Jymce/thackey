"""Weakness-profile pipeline: keystroke events -> scores -> top weaknesses.

Score blends error rate and latency (relative to the user's own median), then
merges into the stored profile with exponential decay so the profile tracks
*current* ability — improved keys fall off the weakness list quickly.
"""
import statistics
from datetime import timedelta

from django.utils import timezone

from analytics.keyboards import DIGITS, PUNCTUATION, finger_for
from analytics.models import WeaknessProfile

DECAY = 0.65          # weight kept from old profile after each new session
NEW_WEIGHT = 1 - DECAY
MIN_CHAR_SAMPLES = 3  # below this, data is noise
MIN_BIGRAM_SAMPLES = 2
TOP_N_WEAKNESSES = 10
REPORT_TTL = timedelta(hours=24)


def extract_features(events):
    """events: ordered KeystrokeEvent iterable -> per-char and bigram stats."""
    char_stats = {}   # char -> [n, errors, latency_sum]
    bigram_stats = {} # "ab" -> [n, errors, latency_sum]
    prev_char = None
    backspaces = 0

    for e in events:
        if e.is_backspace:
            backspaces += 1
            prev_char = None  # error-correction breaks the transition chain
            continue

        ch = (e.expected_char or "").lower()
        if not ch:
            continue
        st = char_stats.setdefault(ch, [0, 0, 0.0])
        st[0] += 1
        st[1] += 0 if e.correct else 1
        if e.latency_ms is not None:
            st[2] += e.latency_ms

        if prev_char is not None and e.latency_ms is not None:
            bg = bigram_stats.setdefault(prev_char + ch, [0, 0, 0.0])
            bg[0] += 1
            bg[1] += 0 if e.correct else 1
            bg[2] += e.latency_ms
        prev_char = ch

    return char_stats, bigram_stats, backspaces


def _score(err_rate, avg_ms, median_ms):
    """0..1 weakness score: 60% error rate, 40% slowness vs own median."""
    if median_ms and avg_ms:
        lat_norm = min(max(avg_ms / median_ms - 1.0, 0.0), 1.5) / 1.5
    else:
        lat_norm = 0.0
    return round(0.6 * err_rate + 0.4 * lat_norm, 4)


def _merge_stats(old_stats, new_stats, min_samples):
    """Exponential-decay merge of {key: {err,ms,n}} dicts; recomputes score."""
    all_keys = set(old_stats) | set(new_stats)
    lats = [
        (new_stats[k][2] / new_stats[k][0])
        for k in new_stats
        if new_stats[k][0] > 0 and new_stats[k][2] > 0
    ] or [v["ms"] for v in old_stats.values() if v.get("ms")]
    median_ms = statistics.median(lats) if lats else 0

    merged = {}
    for k in all_keys:
        old = old_stats.get(k)
        n, err, ms = new_stats.get(k, (0, 0, 0.0))
        new_err = err / n if n else 0.0
        new_ms = ms / n if n and ms else 0.0

        if old:
            err_rate = old["err"] * DECAY + new_err * NEW_WEIGHT if n else old["err"]
            avg_ms = (
                old["ms"] * DECAY + new_ms * NEW_WEIGHT
                if new_ms
                else old.get("ms", 0.0)
            )
            total_n = old.get("n", 0) + n
        else:
            err_rate, avg_ms, total_n = new_err, new_ms, n

        if total_n >= min_samples:
            score = _score(err_rate, avg_ms, median_ms)
        else:
            score = 0.0
        merged[k] = {
            "err": round(err_rate, 4),
            "ms": round(avg_ms, 1),
            "n": total_n,
            "score": score,
        }
    return merged


def _categories(char_scores, layout="qwerty"):
    """Aggregate char scores into hand/finger/symbol buckets."""
    buckets = {
        "left_hand": [], "right_hand": [],
        "pinky": [], "ring": [], "middle": [], "index": [],
        "shift": [], "numbers": [], "punctuation": [],
    }
    for ch, v in char_scores.items():
        if v.get("score", 0) <= 0:
            continue
        info = finger_for(ch, layout)
        if info:
            hand, finger, needs_shift = info
            if hand in ("left", "right"):
                buckets[f"{hand}_hand"].append(v["score"])
                buckets[finger].append(v["score"])
            if needs_shift:
                buckets["shift"].append(v["score"])
        if ch in DIGITS:
            buckets["numbers"].append(v["score"])
        if ch in PUNCTUATION:
            buckets["punctuation"].append(v["score"])
    return {
        k: round(sum(v) / len(v), 4) for k, v in buckets.items() if v
    }


def update_weakness_profile(user, session):
    """Fold one finished session's keystrokes into the user's profile."""
    events = list(session.keystrokes.all())
    if not events:
        return None

    char_stats, bigram_stats, _ = extract_features(events)
    profile, _ = WeaknessProfile.objects.get_or_create(user=user)

    profile.char_scores = _merge_stats(
        profile.char_scores, char_stats, MIN_CHAR_SAMPLES
    )
    profile.bigram_scores = _merge_stats(
        profile.bigram_scores, bigram_stats, MIN_BIGRAM_SAMPLES
    )
    layout = getattr(getattr(user, "settings", None), "keyboard_layout", "qwerty")
    profile.categories = _categories(profile.char_scores, layout)

    candidates = [
        {"type": "char", "key": k, "score": v["score"]}
        for k, v in profile.char_scores.items()
        if v.get("score", 0) > 0 and len(k) == 1
    ] + [
        {"type": "bigram", "key": k, "score": v["score"]}
        for k, v in profile.bigram_scores.items()
        if v.get("score", 0) > 0
    ]
    candidates.sort(key=lambda w: w["score"], reverse=True)
    profile.top_weaknesses = candidates[:TOP_N_WEAKNESSES]

    profile.sessions_analyzed += 1
    profile.save()
    return profile


def session_hotspots(session, limit=6):
    """What THIS one session exposed — returned with the POST /sessions/
    response so the result modal can show it instantly."""
    events = list(session.keystrokes.all())
    if not events:
        return []
    char_stats, bigram_stats, backspaces = extract_features(events)

    lats = [
        n and lat / n
        for (n, err, lat) in char_stats.values()
        if n and lat
    ]
    median_ms = statistics.median(lats) if lats else 0

    spots = []
    for ch, (n, err, lat) in char_stats.items():
        if n < 2:
            continue
        err_rate = err / n
        avg_ms = lat / n if lat else 0
        if err_rate > 0 or (median_ms and avg_ms > median_ms * 1.3):
            spots.append(
                {
                    "type": "char",
                    "key": ch,
                    "err": round(err_rate, 3),
                    "ms": round(avg_ms, 1),
                    "score": _score(err_rate, avg_ms, median_ms),
                }
            )
    for bg, (n, err, lat) in bigram_stats.items():
        if n < 2:
            continue
        err_rate = err / n
        avg_ms = lat / n if lat else 0
        if err_rate > 0.34 or (median_ms and avg_ms > median_ms * 1.8):
            spots.append(
                {
                    "type": "bigram",
                    "key": bg,
                    "err": round(err_rate, 3),
                    "ms": round(avg_ms, 1),
                    "score": _score(err_rate, avg_ms, median_ms),
                }
            )
    spots.sort(key=lambda s: s["score"], reverse=True)
    return spots[:limit]


def compute_strengths(profile, limit=8):
    """Keys/bigrams the user is GOOD at — low score, enough samples."""
    strengths = []
    for kind, stats in (("char", profile.char_scores), ("bigram", profile.bigram_scores)):
        for k, v in stats.items():
            if v.get("n", 0) >= MIN_CHAR_SAMPLES and v.get("score", 0) < 0.15:
                strengths.append({"type": kind, "key": k, "score": v["score"]})
    strengths.sort(key=lambda w: w["score"])
    return strengths[:limit]


def suggest_practice(profile, recent_wpm=None):
    """A tunable practice suggestion — the *starting point* the user can adjust.

    Returns {"targets": [...], "word_count": int, "focus_categories": [...],
             "rationale": str}. Targets are keys the generator should emphasize;
    the UI renders them as toggleable chips so the user can refine the drill
    before generating.
    """
    weaknesses = profile.top_weaknesses
    if not weaknesses:
        return {
            "targets": [],
            "word_count": 50,
            "focus_categories": [],
            "rationale": "Not enough data yet — take a few tests first.",
        }

    targets = [w["key"] for w in weaknesses[:6]]
    cats = sorted(profile.categories.items(), key=lambda kv: kv[1], reverse=True)
    focus_categories = [k.replace("_", " ") for k, _ in cats[:2]]

    # Severity → suggested drill length: worse profile = slightly longer drill
    severity = weaknesses[0]["score"] if weaknesses else 0
    word_count = 75 if severity > 0.4 else 50

    parts = [f"Drill these patterns: {', '.join(t.replace(' ', '␣') for t in targets[:4])}."]
    if focus_categories:
        parts.append(f"Biggest gap: {focus_categories[0]} keys.")
    if recent_wpm and len(recent_wpm) >= 3:
        parts.append("Short focused drills work best — adjust the targets below to taste.")
    return {
        "targets": targets,
        "word_count": word_count,
        "focus_categories": focus_categories,
        "rationale": " ".join(parts),
    }


def build_fallback_report(profile, recent_sessions):
    """Human-readable analysis without any LLM — always available."""
    parts = []
    if not profile.top_weaknesses:
        return "Not enough data yet — take a few tests and come back."

    chars = [w["key"] for w in profile.top_weaknesses if w["type"] == "char"][:3]
    bigrams = [w["key"] for w in profile.top_weaknesses if w["type"] == "bigram"][:3]
    if chars:
        parts.append(f"Weakest keys: {', '.join(chars)}.")
    if bigrams:
        parts.append(f"Slowest letter pairs: {', '.join(bigrams)}.")
    cats = sorted(profile.categories.items(), key=lambda kv: kv[1], reverse=True)
    if cats:
        name = cats[0][0].replace("_", " ")
        parts.append(f"Your biggest category gap is {name} keys.")
    if recent_sessions:
        recent = [s.wpm for s in recent_sessions[:5]]
        older = [s.wpm for s in recent_sessions[5:15]]
        if recent and older:
            delta = statistics.mean(recent) - statistics.mean(older)
            if abs(delta) >= 1:
                direction = "improving" if delta > 0 else "slipping"
                parts.append(
                    f"Recent WPM is {direction} ({delta:+.1f} vs your earlier runs)."
                )
    return " ".join(parts)


def get_progress_report(user, force_refresh=False):
    """Profile + natural-language report. Uses LLM when configured, cached 24h."""
    try:
        profile = user.weakness_profile
    except WeaknessProfile.DoesNotExist:
        return {"profile": None, "report": "No sessions analyzed yet."}

    recent = list(
        user.typing_sessions.order_by("-created_at").values_list("wpm", flat=True)[:15]
    )
    strengths = compute_strengths(profile)
    suggestion = suggest_practice(profile, recent)
    # Regenerate when the profile has newer data than the report — throttled
    # to once per 5 min to protect free-tier LLM quota; also after REPORT_TTL.
    stale = (
        not profile.report_text
        or not profile.report_generated_at
        or (
            profile.updated_at > profile.report_generated_at
            and timezone.now() - profile.report_generated_at > timedelta(minutes=5)
        )
        or timezone.now() - profile.report_generated_at > REPORT_TTL
    )
    if force_refresh or stale:
        text = None
        try:
            from adaptive.llm import summarize_progress

            text = summarize_progress(
                weaknesses=profile.top_weaknesses,
                categories=profile.categories,
                recent_wpm=recent,
            )
        except Exception:
            text = None
        profile.report_text = text or build_fallback_report(
            profile, user.typing_sessions.order_by("-created_at")
        )
        profile.report_generated_at = timezone.now()
        profile.save(update_fields=["report_text", "report_generated_at"])

    return {
        "profile": {
            "char_scores": profile.char_scores,
            "bigram_scores": profile.bigram_scores,
            "categories": profile.categories,
            "top_weaknesses": profile.top_weaknesses,
            "strengths": strengths,
            "sessions_analyzed": profile.sessions_analyzed,
            "updated_at": profile.updated_at,
        },
        "suggestion": suggestion,
        "report": profile.report_text,
    }
