# ThacKey — Living Context

> **Purpose:** This file is the project's shared memory. It tracks current state, decisions, and blockers so any session (human or agent) can pick up where the last left off.
>
> **Update protocol:**
> - Update **Current State** whenever a milestone completes or priorities shift.
> - Append to **Progress Log** after every work session — newest on top. One line per entry: date, what changed.
> - Add to **Decisions Log** whenever a choice is made that affects architecture, deps, or scope. Include *why* — never silently reverse a logged decision; supersede it with a new entry instead.
> - Keep **Next Steps** to ≤5 items, ordered by priority. Check off, don't delete.

## Project Summary

Typing test website where users take timed/word-count tests and receive **AI-driven analytics** identifying their typing weaknesses (specific keys, bigrams, hand/finger patterns), plus **adaptive tests generated around their current progress**. Differentiator vs. Monkeytype/TypeRacer: the feedback loop — analyze → target → retest.

| | |
|---|---|
| Frontend | **Django templates + Tailwind v4 (django-tailwind) + shadcn-style tokens + vanilla JS** — working |
| Backend | Django + Django REST Framework — **built, tests pass** |
| Database | SQLite (PythonAnywhere free tier), MySQL via `DATABASE_URL` on paid |
| Deployment | PythonAnywhere — single process serves pages + API + static |
| Auth | Session auth for pages/API calls from JS; JWT also live for external clients |
| AI | OpenAI-compatible adapter; default Gemini free tier, Groq alt; heuristic fallback |
| Analytics | Keystroke telemetry → weakness scoring → adaptive generation — **implemented** |
| Docs | `architecture.md`, `design.md`, `README.md` |

## Current State

**Phase:** Full-stack v1 working — typing test → save → weakness profile →
adaptive test, all in Django templates.

Pages live: `/` (typing test, anonymous-friendly), `/results/<id>/`,
`/dashboard/`, `/analytics/` (AI report + keyboard heatmap + generate button),
`/register/`, `/login/`. shadcn look via component classes in
`theme/static_src/src/styles.css` (`.btn`, `.card`, `.badge`, `.input`,
`.char-*` typing states). Typing engine: `static/js/typing.js` — keystroke
telemetry, live WPM, session POST with `X-CSRFToken`, adaptive flow via
sessionStorage. Verified end-to-end with curl: register → session POST →
results/analytics render → adaptive generate.

## Progress Log

| Date | Entry |
|---|---|
| 2026-10-25 | Project initialized. Wrote `architecture.md`, `design.md`, `context.md`. Stack confirmed: Next.js/shadcn/Tailwind + Django/DRF + Postgres. |
| 2026-10-25 | Built full backend: 5 apps (accounts, practice, analytics, adaptive, texts), JWT auth, keystroke ingest, weakness pipeline, LLM adapter, tests. Fixed DRF space-trimming bug in keystroke serializer. `pytest`: 24/24 green. Verified live: register → session → profile → adaptive test. |
| 2026-10-25 | Flattened layout — Django project moved from `backend/` to repo root so `manage.py`, `.venv`, and app dirs sit at top level. Recreated venv at root. |
| 2026-10-25 | Added `/` index route (JSON endpoint map) so the bare dev-server URL isn't a 404. |
| 2026-10-25 | **Switched frontend plan: Next.js → Django templates.** Installed django-tailwind (Tailwind v4 standalone binary — no npm needed for builds), created `theme` app + shadcn-style CSS tokens/components, `pages` app (index/results/dashboard/analytics/auth), `static/js/typing.js` engine. `/` JSON index moved to `/api/`; root is now the typing test page. All flows verified. |
| 2026-10-25 | Analytics v2: strengths ("good keys" — green) vs weaknesses (red) on heatmap + badges; new `suggest_practice()` returns a tunable drill (targets/word_count/rationale); `POST /adaptive/generate/` accepts `targets` + `word_count` so the suggestion stays user-adjustable; analytics page renders chips (click to exclude) + length picker. Tests: 33/33 green. |
| 2026-10-25 | LLM wired: Groq key + `openai/gpt-oss-120b`. Found gpt-oss is a reasoning model that returns empty content at small max_tokens — added `reasoning_effort:"low"` (auto-retries without it on 400) + raised token budgets. Verified real LLM passage + coaching report end-to-end. User's key lives in `.env` (gitignored); told user to rotate it since it was briefly committed to `.env.example`. |
| 2026-10-25 | **Bug: sessions silently not saving.** Backspace keystroke events carried `expected_char:""` which the serializer rejected → whole POST 400'd → dashboard/analytics never updated. Fixed: `allow_blank` on expected_char (serializer + model, migrated), backspace events now record the deleted char. Also: report text now regenerates when newer profile data exists (5-min throttle vs 24h-only TTL). Tests: 34/34. |
| 2026-10-25 | **Result modal replaces inline panel.** New `session_hotspots()` returns per-session weak keys/bigrams inside the `POST /sessions/` response (`analysis` field alongside `top_weaknesses` + `suggestion`). typing.js shows client-computed hot spots instantly, then swaps in server data post-save; "practice these" button generates the adaptive test and loads it inline. Tests: 35/35. |

## Decisions Log

| Date | Decision | Why |
|---|---|---|
| 2026-10-25 | Typing engine runs fully client-side; results POSTed at session end | Keystroke latency can't tolerate network round-trips |
| 2026-10-25 | Store raw per-keystroke events (`KeystrokeEvent`) | Granular telemetry is what enables real weakness detection |
| 2026-10-25 | Weakness profile weights recent sessions more (exponential decay) | Requirement: tests must adapt to *current* progress |
| 2026-10-25 | Adaptive generation = heuristic baseline + optional LLM layer | App must work without an API key; LLM adds naturalness + explanations |
| 2026-10-25 | JWT auth (SimpleJWT), stateless API under `/api/v1/` | Clean SPA↔Django separation, no mixed rendering |
| 2026-10-25 | Dark-first design, amber accent, mono font for test text | Typing-tool conventions; mono keeps caret math simple |
| 2026-10-25 | Anonymous users can take tests; auth required only for persistence/analytics | Zero-friction first experience |
| 2026-10-25 | App named `practice/` instead of `sessions/` | `django.contrib.sessions` owns that label (admin needs it); routes keep `/sessions/` |
| 2026-10-25 | LLM adapter = raw `requests` to OpenAI-compatible endpoint, Gemini free tier default | No SDK dep; Groq/OpenRouter/OpenAI all work via env vars; heuristic fallback |
| 2026-10-25 | Deploy target: PythonAnywhere free tier | User requirement; drove SQLite default, WhiteNoise, WSGI-file env config |
| 2026-10-25 | Weakness merge uses 0.65 decay on stored profile | Keeps profile tracking current ability; tuned later if needed |
| 2026-10-25 | Keystroke char fields use `trim_whitespace=False` | DRF trims `' '` to blank otherwise — space keystrokes were rejected |
| 2026-10-25 | **Django templates instead of Next.js** | User request — simpler single deploy on PythonAnywhere; shadcn/ui is React-only so tokens were ported as CSS classes; API kept (session-auth + CSRF from JS, JWT for externals) |
| 2026-10-25 | django-tailwind `4s` variant (standalone binary) | No npm needed to build CSS — works on PythonAnywhere |
| 2026-10-25 | Suggestions are parameters, not fixed tests | `/adaptive/generate/` takes `targets`/`word_count` overrides so users can tune the suggested drill before generating |
| 2026-10-25 | Strengths = score < 0.15 with ≥3 samples | Complements weaknesses; derived on the fly (no new model fields) |

## Open Questions

- ~~LLM provider~~ → settled: **Groq `openai/gpt-oss-120b`** (free tier). Fallback `gpt-oss-20b` or `qwen/qwen3.8-27b` if rate-limited.
- Keyboard layouts beyond QWERTY in v1? (Dvorak/Colemak choices exist in `UserSettings` but only QWERTY is mapped in `analytics/keyboards.py` and the heatmap)
- PythonAnywhere free-tier whitelist: `api.groq.com` must be reachable — check <https://www.pythonanywhere.com/whitelist/> and request it if absent, else the heuristic covers generation.

## Next Steps

1. Add real `LLM_API_KEY` and verify the LLM adaptive/report path end-to-end
2. Polish typing engine: timed modes (15/30/60s countdown), per-word wrapping, replay
3. Settings page (theme, keyboard layout, defaults) — model already exists
4. Deploy to PythonAnywhere per README
5. Dvorak/Colemak key maps + heatmap rows when layouts are confirmed

## Conventions

- Backend: `pytest` + `pytest-django`; Frontend: Vitest for engine, ESLint + Prettier defaults
- File naming: `kebab-case` components, `snake_case` Python
- API versioning: everything under `/api/v1/`
- All agents working on this repo: read this file first, update it before ending a session
