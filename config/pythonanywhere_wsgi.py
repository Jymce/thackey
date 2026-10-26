"""
PythonAnywhere WSGI template.

On PythonAnywhere: Web tab -> edit the WSGI configuration file and REPLACE its
entire contents with this file, adjusting USERNAME and the env vars below.
Then set your virtualenv in the Web tab and hit Reload.
"""
import os
import sys

# --- EDIT THESE ---------------------------------------------------------------
USERNAME = "your-pythonanywhere-username"
PROJECT_DIR = f"/home/{USERNAME}/ThacKey"

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DJANGO_SECRET_KEY"] = "paste-a-long-random-secret-here"
os.environ["DJANGO_DEBUG"] = "false"
os.environ["DJANGO_ALLOWED_HOSTS"] = f"{USERNAME}.pythonanywhere.com"
os.environ["CORS_ALLOWED_ORIGINS"] = "https://your-frontend-domain.com"

# LLM — Gemini free-tier key from https://aistudio.google.com/apikey
# NOTE: PythonAnywhere FREE accounts can only call whitelisted external APIs.
# Check https://www.pythonanywhere.com/whitelist/ — if your provider's host
# isn't listed you can request it be added, or use a paid account.
os.environ["LLM_BASE_URL"] = "https://generativelanguage.googleapis.com/v1beta/openai"
os.environ["LLM_MODEL"] = "gemini-2.5-flash"
os.environ["LLM_API_KEY"] = "paste-your-key-here"

# MySQL on paid tiers only (free tier should leave this unset -> SQLite)
# os.environ["DATABASE_URL"] = f"mysql://{USERNAME}:DBPASS@{USERNAME}.mysql.pythonanywhere-services.com/{USERNAME}$thackey"
# ------------------------------------------------------------------------------

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
