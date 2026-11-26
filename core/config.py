import logging
import os
import secrets

from dotenv import load_dotenv
from fastapi.templating import Jinja2Templates

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger("resumate")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

APP_ENV = (os.getenv("APP_ENV") or "development").strip().lower()
_csrf_default = "true" if (APP_ENV == "production" or os.getenv("VERCEL")) else "false"
CSRF_STRICT = (os.getenv("CSRF_STRICT") or _csrf_default).strip().lower() in ("1", "true", "yes", "on")
REQUESTS_PER_MINUTE = int(os.getenv("REQUESTS_PER_MINUTE") or 120)
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES") or 5_000_000)
FREE_RESUME_DAILY_LIMIT = max(1, int(os.getenv("FREE_RESUME_DAILY_LIMIT") or 3))
CODING_MAX_CODE_CHARS = max(2000, int(os.getenv("CODING_MAX_CODE_CHARS") or 40000))
CODING_MAX_CUSTOM_INPUT_CHARS = max(100, int(os.getenv("CODING_MAX_CUSTOM_INPUT_CHARS") or 10000))
CODING_ASYNC_JUDGE = (os.getenv("CODING_ASYNC_JUDGE") or "true").strip().lower() in ("1", "true", "yes", "on")
CODING_DEEP_INSIGHTS = (os.getenv("CODING_DEEP_INSIGHTS") or "false").strip().lower() in ("1", "true", "yes", "on")
default_hosts = "*" if os.getenv("VERCEL") else "localhost,127.0.0.1,testserver,*.onrender.com,*.vercel.app,*.replit.app"
TRUSTED_HOSTS = [h.strip() for h in (os.getenv("TRUSTED_HOSTS") or default_hosts).split(",") if h.strip()]
ENABLE_HTTPS_REDIRECT = (os.getenv("ENABLE_HTTPS_REDIRECT") or "false").strip().lower() in ("1", "true", "yes", "on")

SENTRY_DSN = (os.getenv("SENTRY_DSN") or "").strip()
if SENTRY_DSN:
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=SENTRY_DSN, environment=APP_ENV, traces_sample_rate=0.1)
        logger.info("Sentry initialized")
    except Exception as e:
        logger.warning("Sentry init failed: %s", e)

session_secret = os.getenv("SESSION_SECRET_KEY") or os.getenv("SESSION_SECRET")
if not session_secret:
    if APP_ENV == "production" or os.getenv("VERCEL"):
        session_secret = secrets.token_urlsafe(32)
        logging.getLogger(__name__).warning("SESSION_SECRET_KEY not configured in production; generated ephemeral key.")
    else:
        session_secret = "dev-only-change-this-secret"

template_dirs = [
    os.path.join(BASE_DIR, "templates"),
    os.path.join(BASE_DIR, "templates", "admin"),
    os.path.join(BASE_DIR, "templates", "auth"),
    os.path.join(BASE_DIR, "templates", "resume"),
    os.path.join(BASE_DIR, "templates", "coding"),
    os.path.join(BASE_DIR, "templates", "interview"),
    os.path.join(BASE_DIR, "templates", "roadmap"),
    os.path.join(BASE_DIR, "templates", "pages"),
]
templates = Jinja2Templates(directory=template_dirs)
templates.env.globals["google_site_verification"] = os.getenv("GOOGLE_SITE_VERIFICATION", "")
