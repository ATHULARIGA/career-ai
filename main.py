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
from core import templates, logger

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", "n/a")
    logger.exception("unhandled_error request_id=%s path=%s", req_id, request.url.path)
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "request_id": req_id},
        status_code=500,
    )

