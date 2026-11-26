import logging
import os
import secrets
from dataclasses import dataclass

from dotenv import load_dotenv
from fastapi.templating import Jinja2Templates

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger("resumate")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _env_bool(key: str, default: str = "false") -> bool:
    return (os.getenv(key) or default).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    """Centralized, typed environment configuration for ResuMate."""

    app_env: str
    is_production: bool
    csrf_strict: bool
    requests_per_minute: int
    max_upload_bytes: int
    free_resume_daily_limit: int
    coding_max_code_chars: int
    coding_max_custom_input_chars: int
    coding_async_judge: bool
    coding_deep_insights: bool
    trusted_hosts: list[str]
    enable_https_redirect: bool
    sentry_dsn: str
    session_secret: str
    gemini_api_key: str
    openai_api_key: str
    groq_api_key: str
    google_client_id: str
    google_client_secret: str
    google_site_verification: str

    @classmethod
    def from_env(cls) -> "Settings":
        app_env = (os.getenv("APP_ENV") or "development").strip().lower()
        is_prod = app_env == "production" or bool(os.getenv("VERCEL"))
        default_hosts = "*" if os.getenv("VERCEL") else "localhost,127.0.0.1,testserver,*.onrender.com,*.vercel.app,*.replit.app"
        trusted_hosts = [h.strip() for h in (os.getenv("TRUSTED_HOSTS") or default_hosts).split(",") if h.strip()]

        secret = os.getenv("SESSION_SECRET_KEY") or os.getenv("SESSION_SECRET")
        if not secret:
            if is_prod:
                secret = secrets.token_urlsafe(32)
                logging.getLogger(__name__).warning("SESSION_SECRET_KEY not configured in production; generated ephemeral key.")
            else:
                secret = "dev-only-change-this-secret"

        return cls(
            app_env=app_env,
            is_production=is_prod,
            csrf_strict=_env_bool("CSRF_STRICT", "true" if is_prod else "false"),
            requests_per_minute=int(os.getenv("REQUESTS_PER_MINUTE") or 120),
            max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES") or 5_000_000),
            free_resume_daily_limit=max(1, int(os.getenv("FREE_RESUME_DAILY_LIMIT") or 3)),
            coding_max_code_chars=max(2000, int(os.getenv("CODING_MAX_CODE_CHARS") or 40000)),
            coding_max_custom_input_chars=max(100, int(os.getenv("CODING_MAX_CUSTOM_INPUT_CHARS") or 10000)),
            coding_async_judge=_env_bool("CODING_ASYNC_JUDGE", "true"),
            coding_deep_insights=_env_bool("CODING_DEEP_INSIGHTS", "false"),
            trusted_hosts=trusted_hosts,
            enable_https_redirect=_env_bool("ENABLE_HTTPS_REDIRECT", "false"),
            sentry_dsn=(os.getenv("SENTRY_DSN") or "").strip(),
            session_secret=secret,
            gemini_api_key=(os.getenv("GEMINI_API_KEY") or "").strip(),
            openai_api_key=(os.getenv("OPENAI_API_KEY") or "").strip(),
            groq_api_key=(os.getenv("GROQ_API_KEY") or "").strip(),
            google_client_id=(os.getenv("GOOGLE_CLIENT_ID") or os.getenv("google_client_id") or "").strip().strip("'\""),
            google_client_secret=(os.getenv("GOOGLE_CLIENT_SECRET") or os.getenv("google_client_secret") or "").strip().strip("'\""),
            google_site_verification=os.getenv("GOOGLE_SITE_VERIFICATION", ""),
        )


settings = Settings.from_env()

APP_ENV = settings.app_env
CSRF_STRICT = settings.csrf_strict
REQUESTS_PER_MINUTE = settings.requests_per_minute
MAX_UPLOAD_BYTES = settings.max_upload_bytes
FREE_RESUME_DAILY_LIMIT = settings.free_resume_daily_limit
CODING_MAX_CODE_CHARS = settings.coding_max_code_chars
CODING_MAX_CUSTOM_INPUT_CHARS = settings.coding_max_custom_input_chars
CODING_ASYNC_JUDGE = settings.coding_async_judge
CODING_DEEP_INSIGHTS = settings.coding_deep_insights
TRUSTED_HOSTS = settings.trusted_hosts
ENABLE_HTTPS_REDIRECT = settings.enable_https_redirect
SENTRY_DSN = settings.sentry_dsn
session_secret = settings.session_secret

if SENTRY_DSN:
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=SENTRY_DSN, environment=APP_ENV, traces_sample_rate=0.1)
        logger.info("Sentry initialized")
    except Exception as e:
        logger.warning("Sentry init failed: %s", e)

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
