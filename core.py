from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv
import os, uuid, time, logging
from collections import defaultdict, deque
from typing import Any, Dict
from features.shared import _same_origin
from db import is_admin_session, current_user_plan
from features.shared.analytics import log_event, log_model_health
load_dotenv()
logger = logging.getLogger("resumate")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
APP_ENV = (os.getenv("APP_ENV") or "development").strip().lower()
CSRF_STRICT = (os.getenv("CSRF_STRICT") or "false").strip().lower() in ("1", "true", "yes", "on")
REQUESTS_PER_MINUTE = int(os.getenv("REQUESTS_PER_MINUTE") or 120)
TRUSTED_HOSTS = [h.strip() for h in (os.getenv("TRUSTED_HOSTS") or "localhost,127.0.0.1,testserver").split(",") if h.strip()] + ["*.onrender.com"]
from features.shared.config import CODING_MAX_CODE_CHARS, CODING_MAX_CUSTOM_INPUT_CHARS, CODING_ASYNC_JUDGE, DEFAULT_PROBLEMS
session_secret = os.getenv("SESSION_SECRET_KEY") or os.getenv("SESSION_SECRET") or "dev-only-change-this-secret"
PUBLIC_PATHS = {"/", "/login", "/signup", "/admin-login", "/healthz"}
PUBLIC_PREFIXES = ["/static", "/api/public"]
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES") or 5_000_000)
FREE_RESUME_DAILY_LIMIT = max(1, int(os.getenv("FREE_RESUME_DAILY_LIMIT") or 3))
app = FastAPI()
templates = Jinja2Templates(directory="templates")
_rate_hits = defaultdict(deque)
class AuthGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/") or "/"
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES): return await call_next(request)
        if request.session.get("user_id") or is_admin_session(request): return await call_next(request)
        return RedirectResponse("/?auth=required", status_code=303)
class RequestGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/static"):
            res = await call_next(request)
            res.headers["Cache-Control"] = "public, max-age=86400"
            return res
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        dq = _rate_hits[ip]
        while dq and now - dq[0] > 60: dq.popleft()
        dq.append(now)
        if len(dq) > REQUESTS_PER_MINUTE: return PlainTextResponse("Too Many Requests", status_code=429)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not _same_origin(request):
             return PlainTextResponse("CSRF validation failed", status_code=403)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        if APP_ENV == "production": response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(RequestGuardMiddleware)
app.add_middleware(AuthGateMiddleware)
app.add_middleware(SessionMiddleware, secret_key=session_secret, https_only=(APP_ENV == "production"), same_site="lax")
@app.get("/healthz")
async def healthz(): return {"status": "ok"}
