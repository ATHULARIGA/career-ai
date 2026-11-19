import time
import uuid
from collections import defaultdict, deque
from fastapi import Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from core.config import APP_ENV, REQUESTS_PER_MINUTE, logger
from core.security import is_admin_session, _same_origin

PUBLIC_PATHS = {
    "/",
    "/login",
    "/signup",
    "/forgot-password",
    "/reset-password",
    "/privacy",
    "/terms",
    "/pricing",
    "/career-map",
    "/roadmap",
    "/mindmap",
    "/skill-info",
    "/healthz",
    "/readyz",
    "/robots.txt",
    "/sitemap.xml",
    "/sitemap",
    "/llms.txt",
    "/openapi.json",
    "/google0159a71a230a2359.html",
    "/resume",
    "/upload",
    "/interview",
    "/coding",
}
PUBLIC_PREFIXES = ("/static", "/roadmap", "/resume", "/.well-known")

_rate_hits = defaultdict(deque)


class AuthGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path or "/"
        normalized_path = path.rstrip("/") or "/"

        if normalized_path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
            return await call_next(request)

        if request.session.get("user_id") or is_admin_session(request):
            return await call_next(request)

        return RedirectResponse("/?auth=required", status_code=303)


class RequestGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path or "/"
        if path.startswith("/static"):
            response = await call_next(request)
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return response

        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = req_id
        ip = ""
        try:
            ip = request.client.host if request.client else "unknown"
        except Exception:
            ip = "unknown"

        # Global abuse throttle.
        now = time.time()
        dq = _rate_hits[ip]
        while dq and now - dq[0] > 60:
            dq.popleft()
        dq.append(now)
        if len(dq) > REQUESTS_PER_MINUTE:
            return PlainTextResponse("Too Many Requests", status_code=429, headers={"X-Request-ID": req_id})

        # CSRF origin guard for state-changing browser requests.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            csrf_exempt = (
                path.startswith("/mindmap")
                or path.startswith("/skill-info")
                or path.startswith("/healthz")
            )
            if not csrf_exempt and not _same_origin(request):
                return PlainTextResponse("CSRF validation failed", status_code=403, headers={"X-Request-ID": req_id})

        started = time.time()
        response = await call_next(request)
        latency_ms = round((time.time() - started) * 1000.0, 1)
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(self), camera=()"
        if path == "/":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://d3js.org https://www.clarity.ms https://*.clarity.ms; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "img-src 'self' data: https: blob: https://*.clarity.ms; "
                "connect-src 'self' https: https://*.clarity.ms; "
                "worker-src 'self' blob:; "
                "object-src 'none'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self';"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://d3js.org https://www.clarity.ms https://*.clarity.ms; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "img-src 'self' data: https: blob: https://*.clarity.ms; "
                "connect-src 'self' https: https://*.clarity.ms; "
                "worker-src 'self' blob:; "
                "object-src 'none'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self';"
            )
        if request.url.scheme == "https" or APP_ENV == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        logger.info("request_id=%s method=%s path=%s status=%s latency_ms=%s", req_id, request.method, path, response.status_code, latency_ms)
        return response


class CachedStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
