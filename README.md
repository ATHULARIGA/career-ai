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

### 💡 Overview
An **AI-powered platform** built to help candidates practice mock interviews and audit resumes for optimal target matching. 

I built this to run fast, local evaluation metrics before hitting LLMs, leveraging rule-based feedback pipelines so users can practice safely.

---

## 🌟 Core Modules

| Module | Purpose | Under The Hood |
| :--- | :--- | :--- |
| **📄 Resume Auditor** | Upload PDF resumes to fetch keyword-gap analysis vs job descriptions. | `GPT-4o`, `pypdf` |
| **🎤 Interview Coach** | Async simulator tracking speech pacing (WPM), filler frequency, and **STAR method** compliance. | `FastAPI`, Token count heuristics |
| **🗺️ Roadmap** | Interactive node graphs mapping prerequisite learning tiers. | `D3.js` |
| **📅 Dispatcher** | Triggers automated schedules with basic email trackers. | `Brevo SMTP` |

---

## 🛠️ Tech Stack

*   **Backend**: `FastAPI` (Python 3.11+)
*   **NLP Evaluation**: `Scikit-learn` (TF-IDF, Cosine Similarity), `OpenAI API`
*   **Visualizations**: `D3.js`
*   **Structure**: `Jinja2` Templates, Minimalist CSS layouts

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
├── templates/         # HTML Templates list
├── static/            # Static weights (CSS/JS)
├── routers/           # FastAPI Endpoints (Auth, Scorer)
├── core.py            # Loggers configs
├── email_sender.py     # Dispatch hook
├── db_backend.py      # ORM / DB Engine
└── main.py            # Main Router setup
```
</details>
