# ResuMate Architecture

## 1. High-Level Request Lifecycle

1. **Middleware Stack (`core/app.py`, `core/middleware.py`)**
   - `HTTPSRedirectMiddleware` (optional via `ENABLE_HTTPS_REDIRECT`)
   - `TrustedHostMiddleware` (configured via `TRUSTED_HOSTS`)
   - `SessionMiddleware` (signed cookies with `HttpOnly`, `SameSite=lax`, and `https_only` in production)
   - `AuthGateMiddleware` (enforces authenticated sessions on non-public routes)
   - `RequestGuardMiddleware` (assigns `X-Request-ID`, enforces rate limits, validates CSRF same-origin on mutating requests, sets `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, and `Strict-Transport-Security`)
2. **Routing Layer (`routers/`)**
   - **Versioned JSON APIs (`routers/api/v1/`):** Pydantic-validated request payloads (`schemas/`) returning structured JSON and raising domain exceptions (`core/exceptions.py`).
   - **SSR & Feature Routers (`routers/*.py`):** Render Jinja2 templates from `templates/` and compose reusable partials/macros from `templates/components/`.
3. **Exception Handling (`main.py`, `core/exceptions.py`)**
   - `AppError` subclasses (`ValidationError`, `UnauthorizedError`, `ForbiddenError`, `NotFoundError`, `RateLimitError`) return consistent JSON errors for `/api/*` or `Accept: application/json` requests and `error.html` for browser page requests.
   - Unexpected exceptions hide raw stack/exception details in production (`APP_ENV=production`) while logging with `request_id`.

## 2. Service & Data Layers

- **Shared AI Provider (`services/ai/provider.py`):**
  - `get_ai_providers()` configures ordered failover: Gemini -> OpenRouter -> Groq.
  - `get_openrouter_client()` provides a single shared OpenRouter client for single-provider services.
  - `invoke_json_llm()` handles JSON-mode completions and fence stripping.
- **Interview Cheat Sheet Pipeline (`services/interview/cheatsheet_generator.py`):**
  - `extract_technologies_from_resume()` detects technologies using `TECH_REGISTRY`, `EXTENDED_TECH_ALIASES`, and dynamic skills-section parsing.
  - `check_tech_used_in_resume()` determines whether a technology appears in resume experience bullets, skills only, or not at all.
  - `_discover_interview_topics_via_ai()` (Stage 1) builds a technology-specific interview syllabus; `_generate_custom_cards_via_ai()` (Stage 2) generates cards covering every syllabus topic, falling back to `CURATED_DECKS` or `build_domain_deterministic_cards()` (`services/interview/cheatsheet_decks.py`).
- **Persistence (`db/backend.py`, `db/repositories/`, `core/database.py`):**
  - Parameterized SQL queries across SQLite and PostgreSQL.
  - Domain repositories live in `db/repositories/` (e.g., `db/repositories/cheatsheets.py`), re-exported by `core/database.py` for backward compatibility.

## 3. Security Controls

- **SSRF Guard (`core/helpers.py`):** `_is_safe_public_url()` restricts job-link scraping to `http`/`https` public IPs and re-validates redirects.
- **Auth & Sessions (`core/security.py`, `routers/auth.py`, `routers/admin.py`):** PBKDF2-SHA256 password hashing, DB-backed auth rate limits, single-use reset tokens via `secrets.token_urlsafe`, constant-time `hmac.compare_digest()` for admin credentials, and `request.session.clear()` on login.
- **Frontend Modules (`static/js/`):** `store.js` (reactive state), `api.js` (JSON fetch wrapper), and `ui.js` (`escapeHtml` XSS prevention and accessible `showToast`).
