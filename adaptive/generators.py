"""Heuristic adaptive-test generator — no external API needed.

Scores each word in the common-word list by how densely it contains the target
chars/bigrams, then samples the top of the weighted pool. Targets come from the
weakness profile by default, but the caller may pass an explicit list — that's
how the "adjust the suggestion then generate" flow works.
"""
import random

from texts.wordlists import WORD_LIST


def _word_score(word, weak_chars, weak_bigrams):
    score = 0
    for c in set(word):
        score += weak_chars.get(c, 0)
    for i in range(len(word) - 1):
        score += weak_bigrams.get(word[i : i + 2], 0) * 2  # bigrams matter more
    return score


def _targets_to_weights(targets):
    """Turn a plain list like ["q", "th"] into score weights by type."""
    weak_chars, weak_bigrams = {}, {}
    for t in targets:
        if not isinstance(t, str):
            continue
        t = t.replace("␣", " ").lower()
        if len(t) == 1:
            weak_chars[t] = 1.0
        elif len(t) >= 2:
            weak_bigrams[t] = 1.0
    return weak_chars, weak_bigrams


def _shown(key):
    return key.replace(" ", "␣")


def generate_heuristic(profile, word_count=50, targets=None, pool_size=150):
    """-> (content, target_patterns, explanation).

    targets: optional explicit pattern list overriding the profile's weakest
    entries (user-tuned suggestion).
    """
    if targets is not None:
        weak_chars, weak_bigrams = _targets_to_weights(targets)
        target_keys = [t.replace("␣", " ") for t in targets]
    else:
        weak_chars = {
            k: v.get("score", 0)
            for k, v in profile.char_scores.items()
            if len(k) == 1 and v.get("score", 0) > 0
        }
        weak_bigrams = {
            k: v.get("score", 0)
            for k, v in profile.bigram_scores.items()
            if v.get("score", 0) > 0
        }
        target_keys = [w["key"] for w in profile.top_weaknesses[:8]]

    if not weak_chars and not weak_bigrams:
        words = random.sample(WORD_LIST, min(word_count, len(WORD_LIST)))
        return " ".join(words), [], "General practice — no weakness data yet."

    scored = sorted(
        WORD_LIST,
        key=lambda w: _word_score(w, weak_chars, weak_bigrams),
        reverse=True,
    )
    pool = [w for w in scored[:pool_size] if _word_score(w, weak_chars, weak_bigrams) > 0]
    if not pool:
        pool = list(WORD_LIST)

    words = random.choices(pool, k=word_count)
    explanation = (
        "Targets your weakest patterns: " + ", ".join(_shown(t) for t in target_keys[:5])
        if target_keys
        else "General practice."
    )
    return " ".join(words), target_keys, explanation
