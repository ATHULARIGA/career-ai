import time
import uuid
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import APP_ENV, REQUESTS_PER_MINUTE, logger
from core.security import _same_origin, get_client_geo, get_client_ip, is_admin_session
from services.analytics.admin_analytics import record_visitor_traffic

PUBLIC_PATHS = {
    "/",
    "/login",
    "/signup",
    "/auth/google",
    "/auth/google/callback",
    "/admin-login",
    "/admin-logout",
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
    "/coding/problems",
    "/book-call",
    "/account",
    "/account/demo",
    "/resume/compare",
    "/resume/compare/demo",
    "/resume/cover-letter/demo",
    "/resume/demo/cover-letter",
    "/resume/demo",
    "/admin/demo",
}
PUBLIC_PREFIXES = ("/static", "/roadmap", "/resume", "/coding", "/admin/demo", "/.well-known", "/auth", "/interview", "/api/interview")

_rate_hits = defaultdict(deque)


class AuthGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path or "/"
        normalized_path = path.rstrip("/") or "/"

        if normalized_path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
            return await call_next(request)

        # Allow demo / audit preview for admin or resume demo routes
        qs = request.scope.get("query_string", b"")
        if isinstance(qs, (bytes, bytearray)):
            qs = qs.decode("utf-8", "ignore")
        if ("demo=true" in qs or "demo=1" in qs or "demo=audit" in qs) and (path.startswith("/admin") or path.startswith("/resume")):
            return await call_next(request)
        if path.startswith("/admin/demo"):
            return await call_next(request)

        if request.session.get("user_id") or is_admin_session(request):
            return await call_next(request)

        if path.startswith("/admin"):
            return RedirectResponse("/admin-login", status_code=303)

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
        ip = get_client_ip(request)

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

        # Asynchronously record visitor traffic with real IP and geographic metadata
        if not (path.startswith("/healthz") or path.startswith("/readyz") or path in ("/favicon.ico", "/robots.txt", "/sitemap.xml")):
            try:
                geo = get_client_geo(request)
                ua = request.headers.get("user-agent", "")
                user_id = "anonymous"
                if "session" in request.scope:
                    session = request.session
                    user_id = str(session.get("user_id") or session.get("user_email") or session.get("admin_user") or "anonymous")
                record_visitor_traffic(
                    ip=ip,
                    country=geo.get("country", "Unknown"),
                    region=geo.get("region", "Unknown"),
                    city=geo.get("city", "Unknown"),
                    path=path,
                    method=request.method,
                    status_code=response.status_code,
                    user_agent=ua,
                    user_id=user_id,
                )
            except Exception:
                pass
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
