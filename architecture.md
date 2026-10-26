# ThacKey — Architecture

Typing test platform with AI-driven weakness analysis and adaptive test generation.

## High-Level Overview

```
┌────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser)                        │
│  Django-rendered HTML + Tailwind CSS + shadcn-style tokens     │
│  + vanilla JS (typing engine, adaptive fetch)                  │
│                                                                │
│  ┌──────────────────┐   ┌───────────────────────────────────┐  │
│  │   Typing Engine  │   │          Templates                │  │
│  │  (static/js/     │   │  test / results / dashboard /     │  │
│  │  typing.js —     │   │  analytics / auth pages           │  │
│  │  keystroke-level │   └───────────────────────────────────┘  │
│  │  telemetry)      │                                          │
│  └────────┬─────────┘                                          │
└───────────┼────────────────────────────────────────────────────┘
            │ REST / JSON (session results, keystroke batches)
            │ — session cookie + CSRF (or JWT for external clients)
            ▼
┌────────────────────────────────────────────────────────────────┐
│                     DJANGO BACKEND                             │
│  Django + Django REST Framework                                │
│                                                                │
│  ┌──────────┐  ┌───────────┐  ┌──────────────┐  ┌───────────┐  │
│  │ accounts │  │ sessions  │  │  analytics   │  │ adaptive  │  │
│  │  (auth)  │  │ (results, │  │  (weakness   │  │ (test     │  │
│  │          │  │ keystroke │  │  profiling)  │  │ generator)│  │
│  │          │  │  ingest)  │  │              │  │           │  │
│  └──────────┘  └───────────┘  └──────┬───────┘  └─────┬─────┘  │
│                                      │                │        │
│                              ┌───────▼────────────────▼─────┐  │
│                              │      Analytics Engine         │  │
│                              │  feature extraction →         │  │
│                              │  weakness scoring →           │  │
│                              │  adaptive text synthesis      │  │
│                              └──────────────┬───────────────┘  │
└─────────────────────────────────────────────┼──────────────────┘
                                              ▼
                                    ┌──────────────────┐
                                    │   PostgreSQL     │
                                    └──────────────────┘
```

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend framework | **Django templates + vanilla JS** | Single codebase, deploys on PythonAnywhere free tier (changed from Next.js — see context.md) |
| Styling | Tailwind CSS v4 via django-tailwind + shadcn-*style* tokens | shadcn/ui is React-only; tokens/components ported as CSS classes (`.btn`, `.card`, `.badge`) |
| Charts | Inline SVG sparkline | No JS chart lib needed for v1 |
| Typing engine | Custom React hook/state machine | Keystroke timing must be sub-millisecond-accurate; runs 100% client-side |
| Backend | Django 5 + Django REST Framework | User-requested; mature ORM, auth, admin |
| Database | PostgreSQL (prod) / SQLite (dev) | JSONB for keystroke payloads; strong aggregation queries for analytics |
| Auth | JWT via `djangorestframework-simplejwt` (HttpOnly cookie option) | Stateless API; pairs cleanly with SPA-style frontend |
| Charts | Recharts (shadcn/ui `Chart` wrapper) | Dashboard WPM/accuracy trends |
| Async jobs | Celery + Redis (phase 2) — start with sync requests | Weakness recalculation can outgrow request cycle |
| AI/LLM (optional) | Provider-agnostic adapter (e.g. OpenAI-compatible endpoint) | Generates natural-language adaptive passages + explanations; system works without it |

## Key Architectural Decisions

### 1. The typing test runs entirely client-side
Keystroke latency can't survive a network round-trip. The frontend typing engine captures every `keydown` with `performance.now()` timestamps, tracks correct/incorrect events, and computes live WPM/accuracy. Only when a test completes does it POST a single payload — summary stats + a batched keystroke event array — to the backend.

### 2. Raw keystroke telemetry is the product's moat
We store per-keystroke events (key, expected char, latency since previous key, correctness, timestamp). This granularity is what enables real weakness detection (specific letters, bigrams, hand alternation) instead of just "you type 42 WPM."

### 3. Analytics is a pipeline, not a page
`ingest → feature extraction → weakness scoring → profile update → adaptive generation`

Each stage is a separate function/module so it can be tested, replaced (heuristics → ML later), and run async.

### 4. Adaptive generation is layered
1. **Baseline:** weighted corpus sampling — pick words/letter clusters that match the user's weak bigrams.
2. **LLM layer (optional):** prompt an LLM with the weakness profile to produce natural sentences emphasizing weak keys, plus a human-readable explanation of what to practice.
3. **Fallback:** if no profile/LLM exists, serve standard word lists (so the app never blocks).

### 5. Dual auth: session cookies + JWT
Template pages use Django session auth; the JS typing engine calls
`/api/v1/` with the session cookie + `X-CSRFToken` header
(`SessionAuthentication` in DRF). JWT endpoints remain for external clients
and a possible future SPA/mobile app.

## Django App Layout

```
repo root (Django project)
├── manage.py, requirements.txt, .env
├── config/              # settings, urls, wsgi/asgi, pythonanywhere_wsgi.py
├── accounts/            # auth views (JWT) + UserSettings
├── practice/            # TypingSession + KeystrokeEvent ingest & retrieval
├── analytics/           # WeaknessProfile, feature extraction, scoring
├── adaptive/            # AdaptiveTest generation (heuristic + LLM adapter)
└── texts/               # TextCorpus / word lists / seed passages
```

> Note: originally named `sessions/` — renamed to `practice/` because
> `django.contrib.sessions` already owns the `sessions` app label (needed by
> Django admin). API routes still use `/sessions/`.

## Data Model (v1)

```
User (accounts)
└── id, username, email, password, created_at
    settings_json  (theme, preferred test length, keyboard layout)

TypingSession (sessions)
└── id, user_id (FK), started_at, finished_at, duration_s,
    mode (time|words|adaptive), source (standard|adaptive),
    wpm, raw_wpm, accuracy, consistency, char_count, error_count
    adaptive_test_id (FK, nullable)

KeystrokeEvent (sessions)
└── id, session_id (FK), seq, expected_char, typed_char,
    correct (bool), latency_ms (time since prev keystroke),
    timestamp_ms, is_backspace

WeaknessProfile (analytics)  — one row per user, updated after each session
└── user_id (FK), updated_at,
    char_scores    JSONB  { "a": {err: 0.03, ms: 142}, ... }
    bigram_scores  JSONB  { "th": {err: 0.01, ms: 96}, ... }
    categories     JSONB  { "left_hand": 0.4, "punctuation": 0.7, ... }
    top_weaknesses JSONB  ranked list for quick reads

AdaptiveTest (adaptive)
└── id, user_id (FK), created_at, generated_by (heuristic|llm),
    content (text), target_patterns JSONB, explanation (text)

TextCorpus (texts)
└── id, body, tags (e.g. "common_words", "code", "quotes"), difficulty
```

`KeystrokeEvent` is the high-volume table — batch-insert via `bulk_create`, index on `(session_id, seq)` and partition/denylist by age if it grows.

## API Surface (REST, `/api/v1/`)

```
POST   /auth/register           POST   /auth/login            POST /auth/logout
GET    /auth/me                 PATCH  /auth/me (settings)

POST   /sessions/               submit finished session + keystroke batch
GET    /sessions/               paginated history
GET    /sessions/{id}/          detail + replay data

GET    /analytics/profile/      current weakness profile
GET    /analytics/trends/       WPM/accuracy time series for dashboard

POST   /adaptive/generate/      build a test from current profile → returns text + rationale
GET    /adaptive/{id}/          fetch generated test

GET    /texts/random/           standard (non-adaptive) test text
```

## Frontend Structure (Django templates)

```
theme/                   # django-tailwind app
├── static_src/src/styles.css   # Tailwind v4 input: shadcn tokens + components
└── static/css/dist/styles.css  # compiled output (tailwind build)

templates/
├── base.html            # nav, theme toggle, CSRF meta
├── pages/               # index (test), results, dashboard, analytics, register
└── registration/login.html

static/js/typing.js      # typing engine: keystroke telemetry, live stats,
                         # session POST, adaptive-test fetch
```

Component classes live in `styles.css` (`.btn`, `.card`, `.badge`, `.input`,
`.kbd`, char states `.char-*`) — the shadcn look without React.

## AI Analytics — Detailed Design

### Feature extraction (per session, post-submit)
From `KeystrokeEvent[]` compute:
- **Per-char stats:** mean latency, error rate, burstiness
- **Bigram/trigram stats:** transition timing between character pairs — catches "slow on `th`/`qu`" that per-char stats miss
- **Hand/finger patterns:** map layout (QWERTY default) → which hand/finger produced the char; detect same-finger repetition stalls
- **Special categories:** punctuation, capitals (shift usage), numbers, bracket pairs
- **Consistency:** latency variance; sudden slowdowns = weak words/patterns

### Weakness scoring
Score each dimension on 0–1 where high = weak:
```
score(char) = w1·normalized_error_rate + w2·normalized_latency(vs user's own median)
```
Weighted more by **recency** (exponential decay over last N sessions) so the profile tracks *current* progress, as requested — improvements push recovered keys off the weakness list quickly.

### Adaptive test generation
- Input: top weakness entries (chars, bigrams, categories)
- Heuristic path: filter `TextCorpus` + word list, weight word selection ∝ density of weak patterns
- LLM path (optional): `system: "Generate a 60-word typing passage emphasizing patterns: th, qu, left-hand alternation; natural English, no rare words."` Store `explanation` so the UI can say *"This test targets your slowest bigrams: th, st, qu."*
- Output → `AdaptiveTest` row → served to frontend like any other text

### Feedback loop
```
session finished → ingest keystrokes → update WeaknessProfile
→ user requests adaptive test → generate → session runs on it → repeat
```

## Non-Functional Concerns

- **Latency:** typing itself = 0 network calls; API calls happen at session end
- **Payload size:** a 60s test ≈ 300–400 keystroke events (~30KB JSON) — fine to inline; add compression later if needed
- **Privacy:** keystroke data is biometric-adjacent — never log raw streams; allow account/data deletion
- **Rate limiting:** throttle `/sessions/` POST and `/adaptive/generate/` (LLM calls cost money)
- **Testing:** `pytest` + `pytest-django` backend; Vitest for `typing-engine`; Playwright for E2E later

## Deployment (target)

```
PythonAnywhere ─────── everything (Django WSGI; free tier → SQLite + WhiteNoise)
                        one process serves templates + API + static files
```

Single-deploy simplicity was the point of moving to Django templates — no
separate frontend host needed. Constraints handled in code: env vars set
inside the WSGI file (`config/pythonanywhere_wsgi.py`), SQLite default,
WhiteNoise serves static (incl. compiled Tailwind), and all outbound LLM
calls degrade gracefully since free-tier accounts only reach whitelisted hosts.

Local dev: `python manage.py tailwind start` (CSS watcher) + `manage.py runserver`.
