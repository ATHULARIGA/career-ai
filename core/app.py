import os
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

from core.config import (
    BASE_DIR,
    APP_ENV,
    TRUSTED_HOSTS,
    ENABLE_HTTPS_REDIRECT,
    session_secret,
)
from core.middleware import (
    RequestGuardMiddleware,
    AuthGateMiddleware,
    CachedStaticFiles,
)
from db.schema import init_all_schemas

app = FastAPI()

app.mount("/static", CachedStaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
app.add_middleware(RequestGuardMiddleware)
app.add_middleware(AuthGateMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
    https_only=(APP_ENV == "production"),
    same_site="lax",
    max_age=60 * 60 * 24 * 14,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=TRUSTED_HOSTS or ["*"])
if ENABLE_HTTPS_REDIRECT:
    app.add_middleware(HTTPSRedirectMiddleware)

# Initialize application tables and seed default state
def init_all_tables() -> None:
    init_all_schemas()


# On serverless environments (e.g. Vercel), schemas are pre-initialized;
# skip serial DDL checks on cold starts to prevent timeout.
if not (os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME")):
    init_all_tables()
