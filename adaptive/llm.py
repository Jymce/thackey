"""Provider-agnostic LLM client over the OpenAI-compatible chat-completions API.

Works with any endpoint that accepts Bearer auth + {model, messages}:
  - Google Gemini free tier:  https://generativelanguage.googleapis.com/v1beta/openai
  - Groq free tier:           https://api.groq.com/openai/v1
  - OpenRouter free models:   https://openrouter.ai/api/v1
  - OpenAI:                   https://api.openai.com/v1

Everything degrades gracefully: no key or any failure -> returns None and the
caller falls back to the heuristic generator.
"""
import json
import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def is_configured():
    return bool(settings.LLM_API_KEY)


def _chat(messages, max_tokens=1500, temperature=0.7):
    if not is_configured():
        return None
    payload = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    # Reasoning models (e.g. Groq gpt-oss) burn the token budget on internal
    # reasoning and return empty content unless this is kept low.
    effort = getattr(settings, "LLM_REASONING_EFFORT", "low")
    if effort:
        payload["reasoning_effort"] = effort
    try:
        resp = requests.post(
            f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        # retry once without reasoning_effort if the provider rejects it
        if resp.status_code == 400 and "reasoning_effort" in payload:
            payload.pop("reasoning_effort")
            resp = requests.post(
                f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        logger.exception("LLM request failed")
        return None


def _extract_json(text):
    """Parse JSON even if the model wraps it in markdown fences."""
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except (ValueError, TypeError):
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except ValueError:
                return None
    return None


def generate_adaptive_text(weaknesses, word_count=50):
    """Ask the LLM for a practice passage targeting the weak patterns.

    Returns {"text": str, "explanation": str} or None.
    """
    targets = ", ".join(w.replace(" ", "␣") for w in weaknesses[:10]) or "general fluency"
    raw = _chat(
        [
            {
                "role": "system",
                "content": (
                    "You generate typing-practice passages. Reply with ONLY a JSON "
                    'object: {"text": "...", "explanation": "..."}.'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Write a typing-practice passage of about {word_count} words. "
                    f"It must densely use these character patterns: {targets}. "
                    "Use common English words, lowercase only, no rare vocabulary, "
                    "no numbers or special punctuation. In 'explanation', one short "
                    "sentence telling the typist what this passage drills."
                ),
            },
        ],
        max_tokens=1500,
        temperature=0.8,
    )
    data = _extract_json(raw)
    if not data or not data.get("text"):
        return None
    text = " ".join(str(data["text"]).split())  # normalize whitespace
    if len(text.split()) < 15:  # too short to be a real passage — treat as failure
        return None
    return {"text": text, "explanation": str(data.get("explanation", ""))}


def summarize_progress(weaknesses, categories, recent_wpm):
    """Natural-language analysis of the user's current progress. str or None."""
    weak_str = ", ".join(
        f"{w['key'].replace(' ', '␣')} ({w['type']})" for w in weaknesses[:8]
    ) or "none yet"
    cat_str = ", ".join(
        f"{k.replace('_', ' ')}: {v:.0%}" for k, v in categories.items()
    ) or "no data"
    wpm_str = ", ".join(f"{w:.0f}" for w in recent_wpm[:10]) or "no sessions"

    raw = _chat(
        [
            {
                "role": "system",
                "content": (
                    "You are a concise typing coach. 2-4 sentences max. Be specific "
                    "about what to practice and note any improvement trend. No fluff."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Weakest patterns: {weak_str}\n"
                    f"Category scores (higher = weaker): {cat_str}\n"
                    f"Recent WPM (newest first): {wpm_str}\n"
                    "Summarize what this typist should focus on right now."
                ),
            },
        ],
        max_tokens=800,
        temperature=0.4,
    )
    return raw.strip() if raw else None
