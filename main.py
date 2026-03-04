from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from resume_parser import extract_text
from scoring import score_resume
from interview_engine import generate_questions
import time
from booking_db import save_booking, get_bookings
from email_sender import send_mail
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from grader import grade_answer
from mindmap_generator import generate_mindmap
from fastapi.responses import JSONResponse



def normalize_question(q):

    if isinstance(q, dict):
        q = q.get("question", "")

    q = str(q)
    q = q.replace("\n", " ")
    q = q.replace("Question:", "")
    q = q.strip()

    return q


app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(SessionMiddleware, secret_key="supersecret")

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
        report = {
            "Error": str(e),
            "Score": "N/A",
            "Feedback": "Please try a different file format."
        }

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

    questions = generate_questions(topic)

    # 🔥 FORCE CLEAN STRINGS
    questions = [normalize_question(q) for q in questions]

    request.session["questions"] = questions
    request.session["ideal"] = []
    request.session["current"] = 0
    request.session["scores"] = []

    return templates.TemplateResponse("interview.html", {
        "request": request,
        "questions": questions,
        "current": 0
    })

@app.post("/evaluate", response_class=HTMLResponse)
def evaluate(request: Request,
             question: str = Form(...),
             answer: str = Form(...)):

    questions = request.session.get("questions", [])
    ideal = request.session.get("ideal", [])
    current = request.session.get("current", 0)
    scores = request.session.get("scores", [])

    question = normalize_question(question)

    from ideal_generator import generate_ideal_answer

    if current >= len(ideal):

        new_ideal = generate_ideal_answer(question)
        new_ideal = normalize_question(new_ideal)

        ideal = ideal + [new_ideal]   # 🚨 IMPORTANT
        request.session["ideal"] = ideal

    ideal_answer = request.session["ideal"][current]

    print("\n======================")
    print("QUESTION:", question)
    print("IDEAL ANSWER:", ideal_answer)
    print("USER ANSWER:", answer)

    if ideal_answer is None:
        print("🚨 IDEAL IS NONE")

    if ideal_answer == "Ideal answer failed":
        print("🚨 IDEAL GENERATION FAILED")

    if answer.strip() == "":
        print("🚨 USER ANSWER EMPTY")

    result = grade_answer(answer, ideal_answer)

    print("SCORE:", result)
    print("======================\n")

    scores = scores + [result]
    current += 1

    request.session["current"] = current
    request.session["scores"] = scores

    finished = current >= len(questions)
    final_score = None

    if finished:
        total = sum([s["correctness"] for s in scores])
        final_score = round(total / len(scores), 1)
        current = len(questions) - 1

    print("QUESTION:", question)
    print("IDEAL:", ideal_answer)
    print("ANSWER:", answer)

    return templates.TemplateResponse(
        "interview.html", {
            "request": request,
            "questions": questions,
            "current": current,
            "feedback": result,
            "finished": finished,
            "final_score": final_score
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


@app.get("/career-map", response_class=HTMLResponse)
def career_map_page(request: Request):
    return templates.TemplateResponse("mindmap.html", {"request": request})


@app.post("/mindmap")
async def create_mindmap(role: str = Form(...)):
    try:
        data = generate_mindmap(role)
        return JSONResponse(content=data)
    except Exception as e:
        print(f"Error generating mindmap: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ADMIN
@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    data = get_bookings()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "data": data
    })
