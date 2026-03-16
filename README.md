# 🚀 ResuMate | AI-Powered Career Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/)
[![Jinja2](https://img.shields.io/badge/Jinja2-B41712?style=for-the-badge&logo=jinja&logoColor=white)](https://jinja.palletsprojects.com/)

An **AI-powered career development platform** designed to help users land their dream job with precision. Includes automated resume parsing, interactive mock interviews, and role-based skill roadmaps.

---

## 🌟 Main Features

### 📄 AI Resume Analyzer
*   **PDF Upload Support**: Automatically extracts text structure from standard CV formats.
*   **AI Scoring**: Reviews keyword matches, layout weight, and provides structural scores out of 10.
*   **Keyword Gap Analysis**: Highlights missing phrases optimized for ATS (Applicant Tracking Systems).

### 🎤 AI Interview Simulator
*   **Dynamic Questions**: Generates contextual behavior & technical questions tailored to role benchmarks.
*   **Answer Evaluation**: Grades user inputs in real-time, providing immediate improvement tips.
*   **Hiring Decision Simulation**: Weighs final responses mapped to standard interview scorecards.

### 🗺️ Career Roadmap Generator
*   **Interactive Skill Mindmap**: Renders nodes dynamically mapping prerequisite hierarchies using **D3.js**.
*   **Role-Based Tracks**: Visualizes pathways for Frontend, Backend, Data, or DevOps mastery tiers.

### 📅 Booking & Support
*   **Schedule Sessions**: Simple modular booking form with email triggers support.
*   **Automated Email meeting Links**: Smooth dispatch using **Brevo SMTP** relay bindings.

---

## 🛠️ Tech Stack

*   **Backend**: `FastAPI` (Python)
*   **Frontend templating**: `Jinja2`, `HTML5/CSS3/JS` (Minimalist Notion Style)
*   **AI & NLP Inference**: `OpenAI API`, `Scikit-learn`, `Numpy`
*   **Visualizations**: `D3.js`
*   **Database ORM**: `SQLite` (Default setup), supporting `PostgreSQL` hooks.
*   **Credentials dispatch**: `ItsDangerous`, `Starslette` Session handlers.

---

## ⚙️ Quick Start Installation

Follow these steps to spin up the service locally:

### 1. Clone the Repository
```bash
git clone <repository_url>
cd career-ai
```

### 2. Configure Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Setup Secrets (`.env`)
Create a `.env` file in the root directory and populate your API credentials:

```bash
# Core AI Credits
OPENAI_API_KEY=your_openai_api_key

# Database Setup (Optional - defaults to bookings.db SQLite)
# DATABASE_URL=postgresql://user:pass@host:port/dbname

# SMTP Support (Brevo / SendGrid example)
SENDER_EMAIL=your_verified_sender@email.com
BREVO_API_KEY=your_brevo_api_key
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587

# Admin Dashboard Defaults
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin_secure_password
ADMIN_EMAIL=admin@platform.com
```

---

## 🖥️ Running the Application

To start the local Uvicorn development server:

```bash
uvicorn main:app --reload
```

The app will become available at: **[`http://localhost:8000`](http://localhost:8000)**

*(Optional)* Access the Admin View area:
*   Route: `/admin`
*   Credentials preset inside your `.env` variables setup.

---

## 📁 Project Directory Structure

```text
career-ai/
├── templates/         # Jinja2 Layout HTML Templates
├── static/            # Styles (CSS), Layout assets (JS, Images)
├── routers/           # FastAPI Endpoints (Auth, Resume, Admin, Pages)
├── core.py            # Global Configs, Loggers Init
├── email_sender.py     # SMTP Dispatch wrappers
├── db_backend.py      # ORM / DB Engine hooks
├── call_booking.py    # Appointment triggers
└── main.py            # Main Router Setup
```
