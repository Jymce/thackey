# ThacKey

Typing test platform with AI-driven weakness analysis and adaptive test generation.

- Repo root is the Django project (manage.py, config/, app dirs)
- Frontend: **Django templates + Tailwind CSS (django-tailwind) + shadcn-style components** — no separate JS app; `static/js/typing.js` is the typing engine
- Docs: `architecture.md`, `design.md`, `context.md` (living project state — read it first)

## Quickstart (local)

```bash
python -m venv .venv
.venv\Scripts\activate          # PowerShell (Git Bash: source .venv/Scripts/activate)
pip install -r requirements.txt
cp .env.example .env            # then edit values
python manage.py tailwind install   # one-time: downloads the Tailwind binary
python manage.py migrate
python manage.py seed_texts
python manage.py tailwind build     # compile CSS once
python manage.py runserver
```

Site at `http://127.0.0.1:8000/` — take a test, register, watch the analytics
fill in. While editing templates/CSS, run the watcher in a second terminal:

```bash
python manage.py tailwind start
```

API lives at `http://127.0.0.1:8000/api/v1/`. Health check: `/api/v1/health/`.
Admin UI at `/admin/` — `python manage.py createsuperuser` first.

Run tests: `pytest`

## API surface

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/api/v1/auth/register/` | POST | no | create account, returns JWT pair |
| `/api/v1/auth/login/` | POST | no | JWT pair |
| `/api/v1/auth/refresh/` | POST | no | rotate refresh token |
| `/api/v1/auth/logout/` | POST | yes | blacklist refresh token |
| `/api/v1/auth/me/` | GET/PATCH | yes | profile + settings |
| `/api/v1/sessions/` | GET/POST | yes | history / submit session+keystrokes |
| `/api/v1/sessions/{id}/` | GET | yes | session detail + keystroke replay |
| `/api/v1/analytics/profile/` | GET | yes | weakness profile (chars/bigrams/categories) |
| `/api/v1/analytics/trends/` | GET | yes | WPM/accuracy time series |
| `/api/v1/analytics/report/` | GET | yes | profile + natural-language analysis |
| `/api/v1/adaptive/generate/` | POST | yes | build a test targeting weaknesses |
| `/api/v1/adaptive/{id}/` | GET | yes | fetch a generated test |
| `/api/v1/texts/random/` | GET | no | standard test text (`?category=words&count=40` or `quote`) |

### Session submit payload

```json
{
  "mode": "time", "source": "standard",
  "started_at": "2026-10-25T12:00:00Z", "duration_s": 30,
  "wpm": 52.4, "raw_wpm": 58.1, "accuracy": 96.2,
  "char_count": 250, "error_count": 9,
  "keystrokes": [
    {"seq": 0, "expected_char": "t", "typed_char": "t", "correct": true,
     "latency_ms": 142, "timestamp_ms": 142, "is_backspace": false}
  ]
}
```

## Free-tier AI setup

The AI layer is a plug-and-play API key over any **OpenAI-compatible** chat endpoint.

**Recommended: Google Gemini free tier** — no billing, ~1,500 req/day:

1. Get a key at <https://aistudio.google.com/apikey>
2. In `.env`:
   ```
   LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
   LLM_MODEL=gemini-2.5-flash
   LLM_API_KEY=your-key
   ```

**Alternative: Groq free tier** (`console.groq.com` → API Keys):
```
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=openai/gpt-oss-120b     # best quality on the free tier; gpt-oss-20b is the faster fallback
```
Note: gpt-oss is a reasoning model — the adapter sends `reasoning_effort: "low"`
automatically so it doesn't burn its token budget thinking instead of answering.
Set `LLM_REASONING_EFFORT=` (empty) to disable, or use `LLM_MODEL=qwen/qwen3.8-27b`.

No key set? Everything still works — adaptive tests and progress reports fall back to the built-in heuristic generator.

## Deploying to PythonAnywhere

Free tier constraints baked into this project: SQLite by default, WhiteNoise for static files, env vars via WSGI file.

1. **Upload code** — clone the repo in a Bash console (`git clone ...`) or upload a zip.
2. **Virtualenv:**
   ```bash
   mkvirtualenv thackey --python=python3.13
   pip install -r ~/ThacKey/requirements.txt
   python ~/ThacKey/manage.py tailwind install   # downloads Tailwind binary
   ```
3. **Migrate + seed + build:**
   ```bash
   cd ~/ThacKey && python manage.py migrate && python manage.py seed_texts && python manage.py tailwind build && python manage.py collectstatic && python manage.py createsuperuser
   ```
4. **Web tab → Add new web app** → Manual config → pick your Python version. Set the virtualenv path to `~/.virtualenvs/thackey`.
5. **WSGI file** — replace its entire contents with `config/pythonanywhere_wsgi.py`, editing `USERNAME`, `DJANGO_SECRET_KEY`, `CORS_ALLOWED_ORIGINS`, and `LLM_API_KEY`.
6. **Reload** and hit `https://you.pythonanywhere.com/api/v1/health/`.

> **Free-tier caveat — outbound API calls:** PythonAnywhere free accounts can only reach whitelisted hosts (<https://www.pythonanywhere.com/whitelist/>). If your LLM provider's host isn't listed, either request it (they add legit APIs on request) or the heuristic generator covers you meanwhile. All LLM calls degrade gracefully.
