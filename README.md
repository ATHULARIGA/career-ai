<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" />
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white" />
</p>

<h1 align="center">🎯 ResuMate</h1>
<p align="center"><b>AI-Powered Career Prep & Mock Interview Platform</b></p>

<p align="center">
  <a href="https://career-ai-foom.onrender.com/upload">
    <img src="https://img.shields.io/badge/%F0%9F%9A%80%20Live%20Demo-Try%20it%20on%20Render-brightgreen?style=for-the-badge" alt="Live Demo" />
  </a>
</p>

---

### 💡 Why I built this
I needed a way to practice mock interviews that felt accurate without solely relying on generic prompts. 

To make it faster and cheaper than hitting an LLM repeatedly, I built a local text grader in Python using **Scikit-Learn (TF-IDF)** before passing metrics over to GPT. It grades your accuracy and maps speech pacing in real-time.

---

## 🌟 Core Modules

| Module | What it solves | Under The Hood |
| :--- | :--- | :--- |
| **📄 Resume Auditor** | Upload PDF resumes to fetch keyword-gap analysis vs job descriptions for ATS tuning. | `GPT-4o`, `pypdf` |
| **🎤 Interview Coach** | Async simulator tracking speech pacing (WPM), filler frequency, and **STAR method** compliance. | `FastAPI`, `Token heuristics` |
| **🗺️ Roadmap** | Interactive node graphs mapping prerequisite learning tiers. | `D3.js` |

---

## 🛠️ Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend** | `FastAPI` (Python 3.11+), `Uvicorn` |
| **NLP & AI** | `Scikit-learn` (TF-IDF, Cosine Similarity), `OpenAI API` |
| **Visualizations** | `D3.js` |
| **Structure** | `Jinja2` Templates, Minimalist CSS layouts |

---

<details>
<summary><b>⚙️ Local Installation & Secrets Setup</b></summary>

### 1. Configure Workspace
```bash
# Clone and enter
git clone <repository_url>
cd career-ai

# Virtual Env
python -m venv venv
source venv/bin/activate 
pip install -r requirements.txt
```

### 2. Secrets Handling (`.env`)
Populate your API credentials looking similar to:
```bash
OPENAI_API_KEY=your_openai_api_key
# SENDER_EMAIL=your_email_settings
# BREVO_API_KEY=api_setting
```

### 3. Run Dev Mode
To run locally:
```bash
uvicorn main:app --reload
```
Access at: `http://localhost:8000`
</details>

---

<details>
<summary><b>📁 Project Directory Tree</b></summary>

```text
career-ai/
├── routers/              # FastAPI endpoint endpoints
├── static/               # Stylesheets & Assets 
├── templates/            # Jinja2 HTML Layouts
├── tests/                # Pytest suit test cases
├── admin_analytics.py    # Admin Dashboard reporting engine
├── booking_db.py         # Schedule caching & triggers
├── coding_platform.py    # Code Sandbox / job judges
├── core.py               # Logger & app globals init
├── email_sender.py        # Brevo SMTP wrappers
├── grader.py             # TF-IDF Cosine Similarity system
├── interview_engine.py   # Question contexts loops
├── interview_feedback.py  # STAR & WPM analyzer
├── mindmap_generator.py   # D3.js mindset node maps
├── resume_parser.py      # PDF text extractor
├── scoring.py            # AI scoring & weights
├── skill_extractor.py    # Keywords gap analyzer
└── main.py               # Main App router setup
```
</details>
