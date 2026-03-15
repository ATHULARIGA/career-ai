from core import app
from routers import auth, resume, interview, coding, admin, pages

app.include_router(auth.router)
app.include_router(resume.router)
app.include_router(interview.router)
app.include_router(coding.router)
app.include_router(admin.router)
app.include_router(pages.router)

