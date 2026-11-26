# ResuMate (CareerAI)

ResuMate is a FastAPI-based career preparation platform providing AI-assisted resume review and LaTeX tailoring, a conversational mock interview simulator, resume-tailored technology interview cheat sheets, coding practice, career roadmaps, and mentorship booking.

## Project Structure

```text
career-ai/
├── main.py                     # FastAPI entrypoint, router registration, exception handlers
├── core/                       # Config (Settings), app/middleware, security, exceptions, helpers
├── db/
│   ├── backend.py              # SQLite / Postgres connection & query wrapper
│   ├── schema.py               # Table initialization
│   └── repositories/           # Domain-focused persistence repositories (e.g. cheatsheets.py)
├── schemas/                    # Pydantic request/response schemas
├── routers/
│   ├── api/v1/                 # Versioned JSON API endpoints (/api/v1/*)
│   ├── auth.py                 # Login, signup, Google OAuth, password reset
│   ├── resume.py               # Resume upload, scoring, LaTeX fix, comparison
│   ├── interview.py            # Mock interview flow & legacy /api/interview/* routes
│   ├── coding.py               # Coding practice & judge status routes
│   ├── admin.py                # Admin dashboard & user/report management
│   └── pages.py                # Public & account SSR pages
├── services/
│   ├── ai/                     # Shared multi-provider AI factory & JSON LLM helper
│   ├── analytics/              # Admin analytics & traffic tracking
│   ├── booking/                # Call booking & email delivery
│   ├── coding/                 # Coding problem bank, judge jobs, answer grader
│   ├── interview/              # Simulator engine, feedback, cheat sheet generator & decks
│   ├── resume/                 # PDF/text parsing, scoring, skill extraction
│   └── roadmap/                # Career roadmaps & mindmap generator
├── templates/
│   ├── components/             # Reusable Jinja partials & macros (toast, resume_selector)
│   └── ...                     # Feature-grouped Jinja2 templates
├── static/
│   ├── js/                     # Shared frontend modules (store.js, api.js, ui.js)
│   └── styles.css / app.js     # Global styles and client scripts
├── tests/                      # Pytest unit, integration, and security regression suites
└── docs/ARCHITECTURE.md        # Detailed architecture & request lifecycle documentation
```

## Local Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Key Environment Variables

Configured centrally via `Settings.from_env()` in `core/config.py`:

| Variable | Purpose |
| :--- | :--- |
| `APP_ENV` | `development` or `production` |
| `SESSION_SECRET_KEY` | Signing secret for Starlette `SessionMiddleware` (required in production) |
| `CSRF_STRICT` | Strict Origin/Referer enforcement (defaults to `true` in production / Vercel) |
| `TRUSTED_HOSTS` | Comma-separated allowed `Host` headers |
| `GEMINI_API_KEY` | Primary AI provider key (Google AI Studio OpenAI-compatible endpoint) |
| `OPENAI_API_KEY` | OpenRouter API key (secondary AI fallback) |
| `GROQ_API_KEY` | Groq API key (tertiary AI fallback) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth2 sign-in credentials |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` / `ADMIN_EMAIL` | Master admin credentials |
| `DATABASE_URL` | Optional PostgreSQL connection string (defaults to local SQLite) |

## Verification & Quality Checks

```bash
# Run tests
./venv/bin/pytest tests/test_api_v1.py tests/test_security_audit.py tests/test_smoke.py tests/test_jd_extraction.py -q

# Lint & type checks
./venv/bin/ruff check . --exclude venv --target-version py39
./venv/bin/basedpyright --level error core/config.py core/exceptions.py db/repositories/ schemas/ routers/api/ main.py

# Validate frontend JS syntax
node -c static/js/store.js static/js/api.js static/js/ui.js
```
