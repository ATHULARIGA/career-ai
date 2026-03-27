from core import app
from routers import auth, resume, interview, coding, admin, pages

app.include_router(auth.router)
app.include_router(resume.router)
app.include_router(interview.router)
app.include_router(coding.router)
app.include_router(admin.router)
app.include_router(pages.router)

from fastapi import Request
from fastapi.responses import HTMLResponse
from core import templates, logger, APP_ENV

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", "n/a")
    import traceback
    traceback.print_exc()
    logger.exception("unhandled_error request_id=%s path=%s", req_id, request.url.path)
    message = str(exc) if APP_ENV != "production" else ""
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={"request": request, "request_id": req_id, "message": message},
        status_code=500,
    )
