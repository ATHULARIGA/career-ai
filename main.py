from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from resume_parser import extract_text
from scoring import score_resume
from interview_engine import generate_questions, evaluate_answer
import time
from booking_db import save_booking, get_bookings
from email_sender import send_mail
from fastapi.staticfiles import StaticFiles


app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# LANDING PAGE
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# RESUME UPLOAD PAGE
@app.get("/resume", response_class=HTMLResponse)
def resume(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

# UPLOAD ROUTE
@app.post("/upload", response_class=HTMLResponse)
async def upload(request: Request, file: UploadFile = File(...)):
    try:
        content = await file.read()
        text = extract_text(file.filename, content)
        report = score_resume(text)
    except Exception as e:
        report = {"Error": str(e), "Score": "N/A", "Feedback": "Please try a different file format."}
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "report": report
    })

# INTERVIEW PAGE
@app.get("/interview", response_class=HTMLResponse)
def interview(request: Request):
    return templates.TemplateResponse("interview.html", {"request": request})

@app.post("/generate", response_class=HTMLResponse)
def generate(request: Request, topic: str = Form(...)):
    q = generate_questions(topic)
    return templates.TemplateResponse("interview.html", {
        "request": request,
        "questions": q["questions"]
    })

@app.post("/evaluate", response_class=HTMLResponse)
def evaluate(request: Request, answer: str = Form(...)):
    r = evaluate_answer(answer)
    return templates.TemplateResponse("interview.html", {
        "request": request,
        "report": r
    })

# BOOK CALL
@app.get("/book-call", response_class=HTMLResponse)
def book(request: Request):
    return templates.TemplateResponse("book_call.html", {"request": request})

@app.post("/schedule", response_class=HTMLResponse)
def schedule(request: Request,
             name: str = Form(...),
             email: str = Form(...),
             topic: str = Form(...),
             datetime: str = Form(...)):

    room = f"mock-{topic}-{int(time.time())}"
    link = f"https://meet.jit.si/{room}"

    save_booking(name, email, topic, datetime, link)
    send_mail(email, link)

    return templates.TemplateResponse("book_call.html", {
        "request": request,
        "link": link
    })

# ADMIN
@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    data = get_bookings()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "data": data
    })
