from core import app
from routers import admin, auth, coding, interview, pages, resume
from routers.api.v1 import api_v1_router

app.include_router(api_v1_router)
app.include_router(auth.router)
app.include_router(resume.router)
app.include_router(interview.router)
app.include_router(coding.router)
app.include_router(admin.router)
app.include_router(pages.router)

for _route in app.routes:
    if hasattr(_route, "methods") and _route.methods and "GET" in _route.methods and "HEAD" not in _route.methods:
        _route.methods.add("HEAD")

from fastapi import Request
from fastapi.responses import JSONResponse

from core import APP_ENV, logger, templates
from core.exceptions import AppError


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    req_id = getattr(request.state, "request_id", "n/a")
    accept_header = request.headers.get("accept", "")
    if request.url.path.startswith("/api/") or "application/json" in accept_header:
        return JSONResponse(
            {"error": exc.message, "code": exc.code, "request_id": req_id},
            status_code=exc.status_code,
        )
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={"request": request, "request_id": req_id, "message": exc.message},
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", "n/a")
    logger.exception("unhandled_error request_id=%s path=%s", req_id, request.url.path)

    is_prod = APP_ENV == "production"
    safe_msg = "An unexpected error occurred. Please try again." if is_prod else (str(exc) or "An unexpected error occurred. Please try again.")
    safe_html_msg = "An unexpected error occurred. Please try again." if is_prod else f"{type(exc).__name__}: {exc!s}"

    # Return clean JSON errors for API routes or JSON requests so clients can handle them properly
    accept_header = request.headers.get("accept", "")
    if request.url.path.startswith("/api/") or "application/json" in accept_header:
        return JSONResponse(
            {
                "error": safe_msg,
                "request_id": req_id,
            },
            status_code=500,
        )

    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={"request": request, "request_id": req_id, "message": safe_html_msg},
        status_code=500,
    )

