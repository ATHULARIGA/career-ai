"""
Technology Interview Cheat Sheet Generator for ResuMate Mock Interview.
Generates interactive, resume-tailored technical interview cheat sheets
with category filters, answers, code snippets, real-world use cases,
interview tips, and revision tracking.
"""

import re
import json
import os
from typing import Any, Dict, List, Optional, Tuple
from openai import OpenAI
from services.interview.cheatsheet_decks import (
    EXTRA_CURATED_DECKS,
    build_domain_deterministic_cards,
)

# ---------------------------------------------------------------------------
# Canonical Technology Knowledge Base
# ---------------------------------------------------------------------------
TECH_REGISTRY: Dict[str, Dict[str, Any]] = {
    "fastapi": {
        "canonical": "FastAPI",
        "category": "Backend Framework",
        "aliases": ["fastapi", "fast-api", "fast api"],
    },
    "python": {
        "canonical": "Python",
        "category": "Programming Language",
        "aliases": ["python", "python3", "py"],
    },
    "react": {
        "canonical": "React",
        "category": "Frontend Framework",
        "aliases": ["react", "react.js", "reactjs"],
    },
    "postgresql": {
        "canonical": "PostgreSQL",
        "category": "Database",
        "aliases": ["postgresql", "postgres", "psql"],
    },
    "sql": {
        "canonical": "SQL",
        "category": "Database",
        "aliases": ["sql", "rdbms", "relational database"],
    },
    "docker": {
        "canonical": "Docker",
        "category": "DevOps & Containers",
        "aliases": ["docker", "containerization", "containers", "dockerfile"],
    },
    "kubernetes": {
        "canonical": "Kubernetes",
        "category": "Cloud & DevOps",
        "aliases": ["kubernetes", "k8s", "kubectl"],
    },
    "redis": {
        "canonical": "Redis",
        "category": "Caching & In-Memory",
        "aliases": ["redis", "in-memory cache"],
    },
    "aws": {
        "canonical": "AWS",
        "category": "Cloud Infrastructure",
        "aliases": ["aws", "amazon web services", "ec2", "s3", "lambda"],
    },
    "git": {
        "canonical": "Git",
        "category": "Developer Tools",
        "aliases": ["git", "github", "version control"],
    },
    "system_design": {
        "canonical": "System Design",
        "category": "Architecture",
        "aliases": ["system design", "distributed systems", "microservices"],
    },
    "kafka": {
        "canonical": "Apache Kafka",
        "category": "Messaging & Streaming",
        "aliases": ["kafka", "apache kafka", "event streaming"],
    },
    "nodejs": {
        "canonical": "Node.js",
        "category": "Backend Runtime",
        "aliases": ["node", "node.js", "nodejs"],
    },
    "typescript": {
        "canonical": "TypeScript",
        "category": "Programming Language",
        "aliases": ["typescript", "ts"],
    },
    "graphql": {
        "canonical": "GraphQL",
        "category": "API Technology",
        "aliases": ["graphql", "gql"],
    },
    "django": {
        "canonical": "Django",
        "category": "Backend Framework",
        "aliases": ["django", "django-rest-framework", "drf"],
    },
    "mongodb": {
        "canonical": "MongoDB",
        "category": "NoSQL Database",
        "aliases": ["mongodb", "mongo"],
    },
}

# ---------------------------------------------------------------------------
# High-Quality Curated Card Decks
# ---------------------------------------------------------------------------
CURATED_DECKS: Dict[str, List[List[str]]] = {
    "fastapi": [
        [
            "Basics",
            "App and running",
            "FastAPI is a modern, high-performance Python framework for building APIs. It is built on Starlette for the web routing and middleware layer, and Pydantic for data validation. It leverages standard Python type hints for automatic request validation, serialization, and interactive OpenAPI documentation at /docs. I run it with Uvicorn, an ASGI server.",
            "from fastapi import FastAPI\napp = FastAPI(title=\"Shop API\")\n\n@app.get(\"/\")\ndef root():\n    return {\"msg\": \"hello\"}\n\n# run: uvicorn main:app --reload",
            "Any JSON/REST backend: microservices, ML model serving, mobile backends.",
            "Stack architecture: Uvicorn (ASGI server) -> Starlette (routing, middleware) -> Pydantic (data parsing). FastAPI adds dependency injection and OpenAPI on top.",
        ],
        [
            "Basics",
            "HTTP methods",
            "A path operation is a URL path plus an HTTP method plus the function that handles it. I use GET to read, POST to create, PUT to replace, PATCH to update part of a resource, and DELETE to remove it. In FastAPI each is declared via a decorator like @app.get or @app.post.",
            "@app.post(\"/items\", status_code=201)\ndef create(item: Item): ...\n\n@app.put(\"/items/{id}\")\ndef replace(id: int, item: Item): ...\n\n@app.delete(\"/items/{id}\", status_code=204)\ndef remove(id: int): ...",
            "CRUD endpoints for any REST resource.",
            "PUT is an idempotent full replacement; PATCH is partial (use model_dump(exclude_unset=True)).",
        ],
        [
            "Requests",
            "Path parameters",
            "Path parameters are variables embedded inside the URL path, like /users/{user_id}. Declaring type hints automatically parses and validates them, returning a 422 Unprocessable Entity if invalid. I use Path() to add constraints like gt=0.",
            "from fastapi import Path\n\n@app.get(\"/users/{user_id}\")\ndef get_user(user_id: int = Path(gt=0)):\n    return {\"id\": user_id}",
            "Identifying a specific resource, e.g. /users/42.",
            "Always declare static routes like /users/me before dynamic routes like /users/{user_id}, otherwise 'me' will be parsed as an id.",
        ],
        [
            "Requests",
            "Query parameters",
            "Query parameters follow the question mark in URLs, like ?limit=10. Any function argument not declared in the path or as a Pydantic model is treated as a query parameter. Defaults make them optional. Query() adds validation like min_length.",
            "from fastapi import Query\n\n@app.get(\"/search\")\ndef search(q: str = Query(min_length=2),\n           limit: int = 10,\n           tags: list[str] = Query([])):\n    return {\"q\": q, \"limit\": limit}",
            "Filtering, sorting, and pagination across collections.",
            "Path identifies a resource; Query filters or modulates it.",
        ],
        [
            "Requests",
            "Request body & Pydantic",
            "The request body is JSON sent by the client. I define its structure using a Pydantic model declared as a parameter. FastAPI parses the body, validates every field against type hints, and auto-documents the schema in /docs.",
            "from pydantic import BaseModel\n\nclass Item(BaseModel):\n    name: str\n    price: float\n    tax: float | None = None\n\n@app.post(\"/items\")\ndef create(item: Item):\n    return item",
            "Creating or updating resources with structured JSON payloads.",
            "Rule of thumb: name in path -> path param; Pydantic model -> body; primitive type -> query param.",
        ],
        [
            "Validation",
            "Pydantic V2 validation",
            "Pydantic validates input using type hints. In Pydantic v2, rules are configured via Field() and custom validators using @field_validator. Validation errors automatically return detailed 422 JSON errors pinpointing exact field locations.",
            "from pydantic import BaseModel, Field, field_validator\n\nclass User(BaseModel):\n    name: str = Field(min_length=3)\n    age: int = Field(ge=18, le=100)\n    email: str\n\n    @field_validator(\"email\")\n    @classmethod\n    def chk_email(cls, v):\n        if \"@\" not in v:\n            raise ValueError(\"invalid email\")\n        return v.lower()",
            "Enforcing business invariants before endpoint execution.",
            "Key v1 to v2 differences: @validator -> @field_validator, .dict() -> .model_dump(), and orm_mode -> from_attributes.",
        ],
        [
            "Validation",
            "Response model filtering",
            "response_model tells FastAPI the expected output schema. FastAPI filters the outgoing data, validates it, and generates the OpenAPI response schema. This prevents accidental leakage of internal fields like hashed passwords.",
            "class UserIn(BaseModel):\n    name: str\n    password: str\n\nclass UserOut(BaseModel):\n    name: str\n\n@app.post(\"/users\", response_model=UserOut)\ndef create(user: UserIn):\n    return user  # password stripped automatically",
            "Protecting sensitive database fields and guaranteeing API contracts.",
            "Separate In, Out, and DB schemas. Use response_model_exclude_unset to avoid emitting unassigned defaults.",
        ],
        [
            "Errors",
            "Status codes & HTTPException",
            "I set successful status codes with status_code on the path decorator. When business logic fails, I raise HTTPException with a numeric status code and a descriptive detail, terminating function execution cleanly.",
            "from fastapi import HTTPException\n\n@app.get(\"/items/{id}\")\ndef read(id: int):\n    if id not in db:\n        raise HTTPException(status_code=404, detail=\"Item not found\")\n    return db[id]",
            "404 for missing resources, 403 for forbidden actions, 409 for unique conflicts.",
            "Memorize common codes: 200 OK, 201 Created, 204 No Content, 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 Unprocessable Entity, 500 Internal Error.",
        ],
        [
            "Structure",
            "Dependency injection (Depends)",
            "Dependency injection allows FastAPI to resolve shared resources before invoking endpoint handlers. I use Depends() for database sessions, authentication, and query parsing. Using yield enables cleanup after the request completes.",
            "from fastapi import Depends\n\ndef get_db():\n    db = SessionLocal()\n    try:\n        yield db\n    finally:\n        db.close()\n\n@app.get(\"/users\")\ndef list_users(db=Depends(get_db)):\n    return db.query(User).all()",
            "Managing database transactions, scoped auth credentials, and shared configurations.",
            "Top interview concept: DI dramatically simplifies unit tests because app.dependency_overrides allows mocking database sessions effortlessly.",
        ],
        [
            "Structure",
            "APIRouter modularization",
            "APIRouter splits monolithic applications into modular sub-routers, each with distinct URL prefixes, tags, and dependencies. Routers are registered on the root app via app.include_router().",
            "# routers/users.py\nrouter = APIRouter(prefix=\"/users\", tags=[\"users\"])\n\n@router.get(\"/\")\ndef list_users(): ...\n\n# main.py\napp.include_router(router)",
            "Structuring scalable production codebases into domain services.",
            "Similar to Blueprints in Flask. Router-level dependencies=[Depends(auth)] protect entire resource groups with a single declaration.",
        ],
        [
            "Security",
            "OAuth2 and JWT tokens",
            "For authentication, I use OAuth2 with Bearer JWT tokens. The client posts credentials to /token, the server returns an HMAC-SHA256 signed JWT with an expiry timestamp, and client requests include it in the Authorization header.",
            "from fastapi.security import OAuth2PasswordBearer\nimport jwt\n\noauth2 = OAuth2PasswordBearer(tokenUrl=\"token\")\n\ndef get_current_user(token: str = Depends(oauth2)):\n    try:\n        payload = jwt.decode(token, SECRET, algorithms=[\"HS256\"])\n        return payload[\"sub\"]\n    except jwt.PyJWTError:\n        raise HTTPException(status_code=401, detail=\"Invalid credentials\")",
            "Securing microservices and single-page application backends.",
            "Always store passwords hashed with bcrypt or argon2. Never store sensitive roles or credentials inside raw unverified JWT payloads.",
        ],
        [
            "Async",
            "async def vs def concurrency",
            "async def endpoints execute directly on the asyncio event loop and require await for non-blocking I/O. Standard def endpoints run inside a separate AnyIO worker threadpool, preventing blocking third-party calls from stalling the main event loop.",
            "@app.get(\"/async\")\nasync def async_fetch():\n    async with httpx.AsyncClient() as client:\n        resp = await client.get(\"https://api.example.com\")\n        return resp.json()\n\n@app.get(\"/sync\")\ndef sync_worker():\n    return time.sleep(1) # runs safely in threadpool",
            "Choosing between async non-blocking drivers vs legacy synchronous libraries.",
            "Classic interview trap: Never call blocking I/O (like requests.get or time.sleep) directly inside an async def function, as it freezes the entire event loop.",
        ],
        [
            "Async",
            "BackgroundTasks",
            "BackgroundTasks allows deferring secondary operations until after the HTTP response has been sent to the client. This keeps response latency low for tasks like sending confirmation emails or audit logs.",
            "from fastapi import BackgroundTasks\n\ndef send_welcome(email: str):\n    # email delivery logic\n    pass\n\n@app.post(\"/register\")\ndef register(email: str, bg: BackgroundTasks):\n    bg.add_task(send_welcome, email)\n    return {\"status\": \"registered\"}",
            "Sending emails, updating search indexes, or logging audit trails.",
            "BackgroundTasks runs in-process. For critical, retry-sensitive, or long-running jobs, use dedicated distributed queues like Celery, BullMQ, or Kafka.",
        ],
        [
            "Test and deploy",
            "Testing with TestClient & pytest",
            "FastAPI applications are tested using Starlette's TestClient powered by HTTPX. TestClient executes in-process without binding a network port, allowing sub-second test execution. Dependencies are swapped via app.dependency_overrides.",
            "from fastapi.testclient import TestClient\nfrom main import app, get_db\n\nclient = TestClient(app)\n\ndef test_read_main():\n    response = client.get(\"/\")\n    assert response.status_code == 200\n    assert response.json() == {\"msg\": \"hello\"}",
            "Unit testing, integration testing, and CI/CD pipelines.",
            "For testing async endpoints or WebSockets with pytest-asyncio, use httpx.AsyncClient with ASGITransport.",
        ],
        [
            "Q&A",
            "Why is FastAPI so fast?",
            "FastAPI runs on ASGI with Starlette and Uvicorn, which process asynchronous I/O concurrently on Python's event loop. In addition, Pydantic v2 executes all schema parsing and validation in compiled Rust, achieving high throughput with minimal overhead.",
            "",
            "Explaining framework performance trade-offs to senior interviewers.",
            "Performance gains are fully realized when underlying database drivers and HTTP clients are truly non-blocking (e.g. asyncpg, httpx).",
        ],
        [
            "Q&A",
            "FastAPI vs Flask vs Django?",
            "Flask is a minimal, synchronous microframework where developers must add validation and API documentation manually. Django is a batteries-included full-stack framework with an integrated ORM and admin interface. FastAPI is purpose-built for APIs: it is async-native, validates inputs via type hints, and automatically generates interactive OpenAPI documentation.",
            "",
            "System architectural reviews and technology selection discussions.",
            "Highlight when to choose each: FastAPI for APIs and microservices, Django for monolithic apps needing admin panels and auth out of the box, Flask for simple scripts.",
        ],
        [
            "Q&A",
            "How do you handle database sessions per request?",
            "I implement a dependency generator with yield that instantiates a scoped session, yields it to the route handler, and closes it inside a finally block. This ensures that every HTTP request has an isolated session that closes even if an unhandled exception occurs.",
            "",
            "Data access patterns and resource lifecycle management.",
            "In modern async FastAPI, use AsyncSession with SQLAlchemy 2.0 and asyncpg for optimal concurrency.",
        ],
    ],
}
CURATED_DECKS.update(EXTRA_CURATED_DECKS)

# ---------------------------------------------------------------------------
# Technology Extraction from Resume
# ---------------------------------------------------------------------------
EXTENDED_TECH_ALIASES: Dict[str, List[str]] = {
    "Apache Spark": ["apache spark", "pyspark", "spark"],
    "Apache Airflow": ["apache airflow", "airflow"],
    "Snowflake": ["snowflake"],
    "dbt": ["dbt", "data build tool"],
    "Terraform": ["terraform", "iac"],
    "Go": ["golang", "go"],
    "Rust": ["rust", "cargo"],
    "Java": ["java", "jvm"],
    "C++": ["c++", "cpp"],
    "C#": ["c#", "csharp", ".net", "dotnet"],
    "Next.js": ["next.js", "nextjs"],
    "Vue.js": ["vue.js", "vuejs", "vue"],
    "Tailwind CSS": ["tailwind", "tailwindcss", "tailwind css"],
    "MySQL": ["mysql"],
    "Elasticsearch": ["elasticsearch", "elastic search", "opensearch"],
    "RabbitMQ": ["rabbitmq"],
    "Linux": ["linux", "ubuntu", "bash"],
    "GCP": ["gcp", "google cloud", "google cloud platform"],
    "Azure": ["azure", "microsoft azure"],
    "BigQuery": ["bigquery"],
    "Databricks": ["databricks"],
    "PyTorch": ["pytorch"],
    "TensorFlow": ["tensorflow"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Scikit-learn": ["scikit-learn", "sklearn"],
    "Flask": ["flask"],
    "Spring Boot": ["spring boot", "springboot"],
    "GitHub Actions": ["github actions"],
    "CI/CD": ["ci/cd", "cicd"],
    "SQLite": ["sqlite"],
    "Fastly": ["fastly"],
    "Nginx": ["nginx"],
    "Jenkins": ["jenkins"],
}

_SKILL_STOPWORDS = {
    "and", "or", "with", "using", "etc", "tools", "languages", "frameworks",
    "databases", "cloud", "platforms", "libraries", "technologies", "skills",
    "technical skills", "core competencies", "software", "engineering", "other",
}


def _clean_skill_token(raw: str) -> str:
    """Normalizes a raw skill token extracted from a resume skills line."""
    tok = re.sub(r"\([^)]*\)", "", raw).strip(" .,:;-•*|/\t\r\n")
    if not tok or len(tok) > 35 or len(tok) < 2:
        return ""
    if tok.lower() in _SKILL_STOPWORDS:
        return ""
    # Skip sentences or prose fragments (> 4 words)
    if len(tok.split()) > 4:
        return ""
    return tok


def extract_technologies_from_resume(resume_text: str, report: Optional[Dict[str, Any]] = None) -> List[str]:
    """
    Extracts all recognized and listed technologies from the candidate's resume text and report.
    Combines canonical registry matching, extended tech aliases, and dynamic skills-line parsing
    so users can select any technology from their resume.
    """
    detected: List[str] = []
    seen_lower = set()

    def _add(name: str) -> None:
        key = re.sub(r"[^a-zA-Z0-9\+\#\.]+", "", name.lower())
        if key and key not in seen_lower:
            seen_lower.add(key)
            detected.append(name)

    full_corpus = (resume_text or "").lower()
    if report and isinstance(report, dict):
        full_corpus += " " + json.dumps(report).lower()

    # 1. Match against canonical registry
    for tech_id, meta in TECH_REGISTRY.items():
        canonical = meta["canonical"]
        aliases = meta.get("aliases", [canonical.lower()])
        for alias in aliases:
            pattern = r"(?:\b|_)" + re.escape(alias) + r"(?:\b|_)"
            if re.search(pattern, full_corpus):
                _add(canonical)
                break

    # 2. Match against extended tech aliases
    for canonical, aliases in EXTENDED_TECH_ALIASES.items():
        for alias in aliases:
            pattern = r"(?:^|[\s,;|/(])" + re.escape(alias) + r"(?:$|[\s,;|/)])"
            if re.search(pattern, full_corpus):
                _add(canonical)
                break

    # 3. Dynamically parse explicit skills lines in resume_text (e.g. "Skills: Python, Airflow, Snowflake")
    if resume_text:
        clean_res = re.sub(r"\\textbf\{([^}]*)\}", r"\1", resume_text)
        clean_res = re.sub(r"\\[a-zA-Z]+\*?\{?", " ", clean_res).replace("}", " ")
        for line in clean_res.splitlines():
            stripped = line.strip()
            lower = stripped.lower()
            if any(k in lower for k in ["skills:", "technologies:", "tools:", "frameworks:", "languages:", "databases:", "platforms:", "stack:", "competencies:"]):
                after_colon = stripped.split(":", 1)[1] if ":" in stripped else stripped
                for part in re.split(r"[,|•;/]+", after_colon):
                    tok = _clean_skill_token(part)
                    if tok:
                        _add(tok)

    # 4. Also inspect structured skill lists in report if available
    if report and isinstance(report, dict):
        for field_key in ("skills", "matched_skills", "extracted_skills", "technologies"):
            vals = report.get(field_key)
            if isinstance(vals, list):
                for item in vals:
                    tok = _clean_skill_token(str(item))
                    if tok:
                        _add(tok)

    # If no resume skills detected, fallback to popular full-stack stack
    if not detected:
        return ["FastAPI", "Python", "PostgreSQL", "Docker", "React"]

    return detected

# ---------------------------------------------------------------------------
# Dynamic AI Generator for All Technologies
# ---------------------------------------------------------------------------
def get_ai_providers() -> List[Tuple[Any, List[str], str]]:
    """
    Returns ordered list of configured AI provider clients, models, and provider labels:
    1. Google Gemini (via OpenAI-compatible endpoint)
    2. OpenRouter (Free models + BYOK fallbacks)
    3. Groq (if configured)
    """
    providers: List[Tuple[Any, List[str], str]] = []

    # 1. Google Gemini (via Google AI Studio OpenAI-compatible endpoint)
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key and gemini_key not in ("dummy", "ci-mock-key"):
        try:
            client = OpenAI(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=gemini_key,
                timeout=25,
                max_retries=0,
            )
            providers.append((
                client,
                ["gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.6-flash"],
                "Gemini",
            ))
        except Exception:
            pass

    # 2. OpenRouter
    openrouter_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openrouter_key and openrouter_key not in ("dummy", "ci-mock-key"):
        try:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key,
                timeout=25,
                max_retries=0,
            )
            providers.append((
                client,
                [
                    "openai/gpt-4o-mini",
                    "meta-llama/llama-3.3-70b-instruct",
                    "google/gemma-4-26b-a4b-it:free",
                ],
                "OpenRouter",
            ))
        except Exception:
            pass

    # 3. Groq
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key and groq_key not in ("dummy", "ci-mock-key"):
        try:
            client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=groq_key,
                timeout=10,
                max_retries=0,
            )
            providers.append((
                client,
                ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
                "Groq",
            ))
        except Exception:
            pass

    return providers


def _invoke_json_llm(
    providers: List[Tuple[Any, List[str], str]],
    prompt: str,
    max_tokens: int = 4000,
) -> Optional[Dict[str, Any]]:
    """
    Calls configured AI providers in order and parses a JSON object response.
    Shared helper used by both interview-topic discovery and card generation.
    """
    for client, models, _provider_name in providers:
        for model in models:
            try:
                response = client.chat.completions.create(
                    model=model,
                    response_format={"type": "json_object"},
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                )
                content = (response.choices[0].message.content or "").strip()
                if not content:
                    continue
                if "```json" in content:
                    content = content.replace("```json", "").replace("```", "").strip()
                if "{" in content and "}" in content:
                    content = content[content.find("{") : content.rfind("}") + 1]
                data = json.loads(content)
                if isinstance(data, dict):
                    return data
            except Exception:
                continue
    return None


def _discover_interview_topics_via_ai(
    tech_name: str,
    role_name: str,
    providers: List[Tuple[Any, List[str], str]],
) -> List[Dict[str, str]]:
    """
    Stage 1 Prompt: Identifies the exact high-signal interview topics and tricky
    real-world questions specifically tested for `tech_name` in `role_name` interviews.
    """
    discovery_prompt = f"""You are a Bar-Raiser Principal Engineer designing an exhaustive technical interview rubric for "{tech_name}" (Target Role: "{role_name}").

Identify the 20 to 24 MOST IMPORTANT, frequently tested interview topics and real-world interview questions specifically for "{tech_name}".
Do NOT list generic filler topics—every topic must reflect what senior interviewers actually grill candidates on for "{tech_name}" specifically (its unique internals, execution engine, data/state model, concurrency/locking, performance tuning, common production failure modes, security pitfalls, trade-offs vs alternatives, and gotcha Q&As).

Ensure balanced coverage across:
- Basics & Core Primitives (2-3 topics)
- Architecture & Deep Internals specific to {tech_name} (4 topics)
- Concurrency, State & Consistency (2-3 topics)
- Performance Tuning, Profiling & Scaling (3 topics)
- Reliability, Debugging & Production Operations (3 topics)
- Security & Hardening (2 topics)
- System Design & When to Choose {tech_name} vs Alternatives (2 topics)
- High-Bar Interview Q&A & Traps (6-7 specific interview questions starting with "Q: ")

Return valid JSON only:
{{
  "topics": [
    {{
      "category": "Basics | Architecture | Concurrency | Performance | Reliability | Security | System Design | Q&A",
      "topic": "Specific {tech_name} topic title (or 'Q: <Exact Interview Question>' for Q&A)",
      "focus": "1-sentence note on the exact internal mechanism, trade-off, or trap interviewers test."
    }}
  ]
}}
No emojis."""

    data = _invoke_json_llm(providers, discovery_prompt, max_tokens=2000)
    if not data:
        return []
    raw_topics = data.get("topics", [])
    if not isinstance(raw_topics, list):
        return []
    cleaned: List[Dict[str, str]] = []
    for item in raw_topics:
        if isinstance(item, dict) and str(item.get("topic", "")).strip():
            cleaned.append({
                "category": str(item.get("category", "Basics")).strip(),
                "topic": str(item.get("topic", "")).strip(),
                "focus": str(item.get("focus", "")).strip(),
            })
    return cleaned


def _generate_custom_cards_via_ai(
    tech_name: str,
    target_role: str = "",
    resume_context: str = "",
    usage_info: Optional[Dict[str, Any]] = None,
) -> List[List[str]]:
    """
    Two-stage multi-provider LLM pipeline:
    1) Discovers the exact high-signal interview topics for `tech_name`.
    2) Generates 22 to 28 production-grade cards covering EVERY discovered topic + Q&A.
    """
    providers = get_ai_providers()
    if not providers:
        return _generate_deterministic_cards(tech_name, target_role)

    # Prepare sanitized resume context (up to 3000 chars)
    clean_resume = re.sub(r"\\[a-zA-Z]+(\[[^\]]*\])?(\{([^}]*)\})?", r"\3", resume_context or "")
    clean_resume = re.sub(r"[\{\}\$\\\#\*\~]", "", clean_resume)
    clean_resume = re.sub(r"\s+", " ", clean_resume).strip()[:3000]

    role_name = target_role.strip() or "Software Engineer"
    tech_clean = tech_name.strip()

    if usage_info is None:
        usage_info = check_tech_used_in_resume(resume_context, tech_clean) if resume_context else {
            "used_in_resume": False,
            "in_experience": False,
            "in_skills_only": False,
            "project_points": [],
            "resume_match_status": "not_found",
        }

    if usage_info.get("in_experience") and usage_info.get("project_points"):
        bullets_preview = "; ".join(
            f"[{pt['context']}] {pt['point']}" for pt in usage_info["project_points"][:4]
        )
        resume_usage_instruction = (
            f"Resume Usage Status: CONFIRMED USED in candidate's work/project experience ({bullets_preview}). "
            f"Tailor 'work_experience' directly to these real resume projects and metrics."
        )
    elif usage_info.get("used_in_resume"):
        resume_usage_instruction = (
            f"Resume Usage Status: LISTED in candidate's resume skills for {role_name}. "
            f"Frame 'work_experience' around realistic {role_name} production scenarios connecting to their resume stack."
        )
    elif clean_resume:
        resume_usage_instruction = (
            f"Resume Usage Status: NOT FOUND on the candidate's resume. "
            f"Do NOT claim or fabricate that the candidate already used {tech_clean} in their past jobs. "
            f"Instead, frame 'work_experience' as how to bridge their existing resume stack to {tech_clean} in {role_name} interviews, "
            f"and give honest interview framing tips."
        )
    else:
        resume_usage_instruction = "Resume Usage Status: No resume provided; tailor for a general senior candidate."

    # Stage 1: Discover technology-specific high-yield interview syllabus
    discovered_topics = _discover_interview_topics_via_ai(tech_clean, role_name, providers)
    if discovered_topics:
        syllabus_lines = "\n".join(
            f"{idx + 1}. [{t['category']}] {t['topic']} — Focus: {t['focus']}"
            for idx, t in enumerate(discovered_topics)
        )
        coverage_instruction = f"""Cover EVERY SINGLE ONE of these {len(discovered_topics)} high-priority interview topics for {tech_clean} (one dedicated card per topic, do not skip any):
{syllabus_lines}"""
    else:
        coverage_instruction = f"""Generate 22 to 28 comprehensive, production-grade interview revision cards across ALL essential interview pillars for {tech_clean}:
- Basics (2-3 cards): Core design philosophy, execution/runtime model, fundamental primitives, and when to choose {tech_clean} over alternatives.
- Architecture (3-4 cards): Deep internals (memory layout, event loop/threading, storage engines, protocols, indexing, scheduling, clustering/partitioning, or rendering pipeline).
- Concurrency (2-3 cards): Concurrent execution, race conditions, async I/O, locking, idempotency, backpressure, or transaction isolation levels.
- Performance (2-3 cards): Latency profiling, memory/CPU optimization, query/index tuning, connection pooling, caching strategies, and scaling bottlenecks.
- Reliability (2-3 cards): Failure modes, retries with exponential backoff and jitter, circuit breaking, graceful shutdown, health checks, observability/debugging, and disaster recovery.
- Security (2 cards): Authentication, authorization (RBAC/ABAC), secrets management, injection/vulnerability prevention, and encryption at rest and in-transit.
- System Design (2 cards): How {tech_clean} fits into large-scale distributed systems, trade-offs vs competing technologies, and capacity/operational trade-offs.
- Q&A (6-8 cards): The most important, frequently asked, and tricky real-world interview questions and model answers for {tech_clean}. Prefix title with "Q: " and start definition with "A: "."""

    prompt = f"""You are a Principal Staff Engineer and Senior Technical Interviewer at top-tier technology companies.
Generate an exhaustive, all-in-one interview cheat sheet deck for: "{tech_clean}".
Target Candidate Role: "{role_name}".
Candidate Resume Context: "{clean_resume if clean_resume else 'General senior candidate'}".
{resume_usage_instruction}

{coverage_instruction}

Return a valid JSON object with this exact structure:
{{
  "cards": [
    {{
      "category": "Category Name (Basics, Architecture, Concurrency, Performance, Reliability, Security, System Design, Q&A)",
      "title": "Concise Technical Topic Title (or 'Q: <Interview Question>' for Q&A)",
      "definition": "Authoritative technical explanation of how it works under the hood, or 'A: <Complete model answer>' for Q&A (3-5 sentences).",
      "code": "Syntactically valid, production-ready snippet, CLI command, or config with best practices (no dummy placeholders).",
      "work_experience": "Concrete real-world production story tailored to the candidate's target role/resume with measurable metrics (e.g. latency, QPS, throughput).",
      "interview_tip": "Actionable guidance on what interviewers look for, follow-up questions they ask, technical terminology to emphasize, and common traps to avoid."
    }}
  ]
}}

Strict requirements:
- For Q&A cards, prefix "title" with "Q: " and start "definition" with "A: ".
- Ensure all string values are properly escaped (newlines as \\n, quotes as \\\").
- Produce syntactically correct code or configuration for {tech_clean}.
- Do NOT use emojis anywhere in the output.
"""

    data = _invoke_json_llm(providers, prompt, max_tokens=6000)
    if data:
        raw_items = data.get("cards", []) if isinstance(data, dict) else []
        parsed_cards = []
        for item in raw_items:
            if isinstance(item, dict):
                c_cat = str(item.get("category", "Basics")).strip()
                c_title = str(item.get("title", "")).strip()
                c_def = str(item.get("definition", "")).strip()
                c_code = str(item.get("code", "")).strip()
                c_work = str(item.get("work_experience", "")).strip()
                c_tip = str(item.get("interview_tip", "")).strip()
                if c_title and (c_def or c_work):
                    parsed_cards.append([c_cat, c_title, c_def, c_code, c_work, c_tip])
            elif isinstance(item, list) and len(item) >= 6:
                parsed_cards.append([str(x) for x in item[:6]])

        if len(parsed_cards) >= 5:
            return parsed_cards

    return _generate_deterministic_cards(tech_name, target_role)


def _detect_technology_domain(tech_name: str) -> str:
    """Classifies a technology into its engineering domain."""
    norm = re.sub(r"[^a-zA-Z0-9]+", "", tech_name.lower().strip())
    meta = TECH_REGISTRY.get(norm, {})
    cat = meta.get("category", "").lower()

    if "database" in cat or any(db in norm for db in ["postgres", "sql", "mongo", "redis", "mysql", "cassandra", "dynamo", "sqlite", "db"]):
        return "database"
    if "streaming" in cat or any(st in norm for st in ["kafka", "rabbit", "queue", "sqs", "event", "stream", "pulsar"]):
        return "streaming"
    if "frontend" in cat or any(fe in norm for fe in ["react", "vue", "angular", "svelte", "next", "tailwind", "css"]):
        return "frontend"
    if "container" in cat or any(co in norm for co in ["docker", "kubernetes", "k8s", "helm", "terraform", "ansible", "ci", "cd"]):
        return "devops"
    if "cloud" in cat or any(cl in norm for cl in ["aws", "gcp", "azure", "cloud"]):
        return "cloud"
    if "framework" in cat or any(fw in norm for fw in ["fastapi", "django", "flask", "express", "nest", "spring", "rails"]):
        return "framework"
    if "runtime" in cat or any(rt in norm for rt in ["node", "deno", "bun"]):
        return "runtime"
    if "language" in cat or any(pl in norm for pl in ["python", "typescript", "javascript", "golang", "go", "rust", "java", "cplusplus", "cpp"]):
        return "language"
    return "general"


def _generate_deterministic_cards(tech_name: str, target_role: str = "") -> List[List[str]]:
    """
    Deterministic domain-aware offline fallback generator for any technology.
    Produces 12-14 rich, structured cards covering all critical interview pillars
    and important Q&A with realistic syntax.
    """
    domain = _detect_technology_domain(tech_name)
    return build_domain_deterministic_cards(tech_name, target_role, domain)


# ---------------------------------------------------------------------------
# Tailoring Cards with Resume Context & Project Bullet Points
# ---------------------------------------------------------------------------
def extract_project_talking_points_for_tech(resume_context: str, tech_name: str) -> List[Dict[str, str]]:
    """
    Extracts candidate projects, work experiences, metrics, and bullet points from
    the resume that utilize or relate to the given technology.
    Completely dynamic - zero hardcoded company or project names.
    """
    if not resume_context or not tech_name:
        return []

    tech_lower = tech_name.lower().strip()
    norm_key = re.sub(r"[^a-zA-Z0-9]+", "", tech_lower)
    aliases = [tech_lower]
    for k, meta in TECH_REGISTRY.items():
        if norm_key == k or norm_key in [re.sub(r"[^a-zA-Z0-9]+", "", a) for a in meta.get("aliases", [])]:
            aliases.extend([a.lower() for a in meta.get("aliases", [])])
            break

    # Clean LaTeX / Markdown formatting
    clean_text = resume_context
    clean_text = re.sub(r"\\resumeSubheading\{([^}]+)\}\{([^}]+)\}\{([^}]+)\}\{([^}]+)\}", r"\n### \1 - \3\n", clean_text)
    clean_text = re.sub(r"\\resumeProjectHeading\{([^}]+)\}\{([^}]+)\}", r"\n### \1\n", clean_text)
    clean_text = re.sub(r"\\[a-zA-Z]+\*?\{?", " ", clean_text)
    clean_text = clean_text.replace("}", " ").replace(r"\\", "\n")

    lines = [ln.strip() for ln in clean_text.splitlines() if ln.strip()]
    matches = []
    current_context = ""

    in_skills_section = False
    for line in lines:
        lower = line.lower()
        if "technical skills" in lower or ("skills" in lower and len(line) < 35 and ":" in line):
            in_skills_section = True
            continue
        if any(sec in lower for sec in ["experience", "employment", "work history", "projects", "key initiatives"]) and len(line) < 40:
            in_skills_section = False
            continue

        if in_skills_section:
            continue

        # Detect dynamic project or company headings
        if (
            line.startswith(("#", "**", "Project:", "Role:", "Company:"))
            or (" | " in line and len(line) < 80)
            or (" – " in line and len(line) < 80 and not line.startswith("-"))
            or (" - " in line and len(line) < 80 and not line.startswith("-"))
        ):
            cleaned_heading = re.sub(r"[\#\*\_\:]", "", line).strip()
            cleaned_heading = re.split(r"\||–|-|,", cleaned_heading)[0].strip()
            if len(cleaned_heading) >= 3 and len(cleaned_heading) <= 45 and not any(h in cleaned_heading.lower() for h in ["skills", "education", "summary", "languages", "tools"]):
                current_context = cleaned_heading

        # Check for tech mention
        if any(re.search(r"(?:\b|_)" + re.escape(alias) + r"(?:\b|_)", lower) for alias in set(aliases)):
            clean_line = re.sub(r"[\#\*\-\t\r]", "", line).strip()
            words = clean_line.split()
            if len(words) >= 5 and not any(h in lower for h in ["languages:", "frameworks:", "tools:", "platforms:", "libraries:"]):
                ctx = current_context or "Production Architecture"
                matches.append({"context": ctx, "point": clean_line})

    seen = set()
    deduped = []
    for m in matches:
        if m["point"] not in seen:
            seen.add(m["point"])
            deduped.append(m)

    return deduped


def check_tech_used_in_resume(resume_context: str, tech_name: str) -> Dict[str, Any]:
    """
    Parses the candidate's resume to determine whether `tech_name` was used in their
    experience/projects, listed in skills only, or not present on the resume.
    """
    if not resume_context or not tech_name:
        return {
            "used_in_resume": False,
            "in_experience": False,
            "in_skills_only": False,
            "project_points": [],
            "resume_match_status": "not_found",
        }

    project_points = extract_project_talking_points_for_tech(resume_context, tech_name)
    if project_points:
        return {
            "used_in_resume": True,
            "in_experience": True,
            "in_skills_only": False,
            "project_points": project_points,
            "resume_match_status": "experience",
        }

    tech_lower = tech_name.lower().strip()
    norm_key = re.sub(r"[^a-zA-Z0-9]+", "", tech_lower)
    aliases = [tech_lower]
    for k, meta in TECH_REGISTRY.items():
        if norm_key == k or norm_key in [re.sub(r"[^a-zA-Z0-9]+", "", a) for a in meta.get("aliases", [])]:
            aliases.extend([a.lower() for a in meta.get("aliases", [])])
            break
    for canonical, ext_aliases in EXTENDED_TECH_ALIASES.items():
        if norm_key == re.sub(r"[^a-zA-Z0-9]+", "", canonical.lower()) or tech_lower in ext_aliases:
            aliases.extend(ext_aliases)
            break

    corpus = resume_context.lower()
    in_resume_text = any(
        re.search(r"(?:^|[\s,;|/(\b_])" + re.escape(alias) + r"(?:$|[\s,;|/)\b_])", corpus)
        for alias in set(aliases)
    )
    if in_resume_text:
        return {
            "used_in_resume": True,
            "in_experience": False,
            "in_skills_only": True,
            "project_points": [],
            "resume_match_status": "skills_only",
        }

    return {
        "used_in_resume": False,
        "in_experience": False,
        "in_skills_only": False,
        "project_points": [],
        "resume_match_status": "not_found",
    }


def tailor_cheatsheet_for_resume(
    cards: List[List[str]],
    resume_context: str = "",
    target_role: str = "",
    tech_name: str = "",
    usage_info: Optional[Dict[str, Any]] = None,
) -> List[List[str]]:
    """
    Enriches cheat sheet cards with personalized candidate talking points
    tailored to whether and how the technology was used in the user's resume.
    """
    if not resume_context and not target_role:
        return cards

    if usage_info is None:
        usage_info = check_tech_used_in_resume(resume_context, tech_name) if resume_context else {
            "used_in_resume": False,
            "in_experience": False,
            "in_skills_only": False,
            "project_points": [],
            "resume_match_status": "not_found",
        }

    project_points = usage_info.get("project_points", [])
    used_in_resume = bool(usage_info.get("used_in_resume"))
    in_skills_only = bool(usage_info.get("in_skills_only"))
    role_mention = target_role or "Software Engineer"
    tailored_cards = []

    point_idx = 0
    num_points = len(project_points)

    for idx, card in enumerate(cards):
        c_cat, c_title, c_say, c_code, c_use, c_tip = card

        if project_points:
            active_pt = project_points[point_idx % num_points]
            point_idx += 1
            ctx_name = active_pt["context"]
            pt_text = active_pt["point"]

            c_use = f"In {ctx_name}: {pt_text}"
            if idx == 0:
                c_tip = f"Resume anchor ({ctx_name}): Mention your experience: '{pt_text}'. Lead with this concrete project outcome when answering! " + c_tip
            elif c_cat == "Q&A":
                c_tip = f"Project talking point ({ctx_name}): Connect this question to: '{pt_text}'. " + c_tip
        elif in_skills_only:
            c_use = f"Listed in your {role_mention} resume skills: Be ready to walk through how you applied {c_title} in production (or a hands-on project) with concrete latency/reliability metrics."
            if idx == 0 and target_role:
                c_tip = f"Resume check: {tech_name or 'This tech'} appears in your skills section without a detailed experience bullet—prepare one crisp 30-second production story. " + c_tip
            elif c_cat == "Q&A":
                c_tip = f"Resume anchor: Connect this {tech_name or 'topic'} question to the closest production project on your resume. " + c_tip
        elif resume_context and not used_in_resume:
            c_use = f"Not listed on your selected resume yet — Recommended {role_mention} framing: Bridge from your existing resume stack and explain how you would apply {c_title} in production."
            if idx == 0:
                c_tip = f"Honest interview framing: {tech_name or 'This technology'} is not on your selected resume. State your transferable foundation from your current stack rather than claiming prior production ownership. " + c_tip
            elif c_cat == "Q&A":
                c_tip = f"Transferable angle: Relate {c_title} to analogous patterns you built in your resume projects. " + c_tip
        elif target_role:
            c_use = f"Recommended application for {role_mention}: Apply {c_title} in production services to eliminate single points of failure and streamline operations."
            if idx == 0:
                c_tip = f"Tailored for your {role_mention} interviews: Lead with measurable outcomes from your projects when explaining this concept. " + c_tip

        tailored_cards.append([c_cat, c_title, c_say, c_code, c_use, c_tip])

    return tailored_cards


# ---------------------------------------------------------------------------
# Main API: Get or Generate Cheatsheet
# ---------------------------------------------------------------------------
def get_cheatsheet_for_technology(
    tech_name: str,
    resume_text: str = "",
    target_role: str = "",
    force_ai: bool = False,
) -> Dict[str, Any]:
    """
    Returns full cheat sheet payload for a technology.
    Dynamically generates via AI for any technology when AI providers are available.
    Falls back gracefully to curated decks or domain-aware deterministic cards
    when running offline or in test environments.
    """
    norm_key = re.sub(r"[^a-zA-Z0-9]+", "", tech_name.lower().strip())
    canonical_name = tech_name.strip()

    # Check canonical registry
    for k, meta in TECH_REGISTRY.items():
        if norm_key == k or norm_key in [re.sub(r"[^a-zA-Z0-9]+", "", a) for a in meta.get("aliases", [])]:
            canonical_name = meta["canonical"]
            norm_key = k
            break

    raw_cards: List[List[str]] = []

    # Check if AI provider is present
    providers = get_ai_providers()
    is_curated = norm_key in CURATED_DECKS

    # Check whether the user actually used this technology in their resume
    usage_info = check_tech_used_in_resume(resume_text, canonical_name) if resume_text else {
        "used_in_resume": False,
        "in_experience": False,
        "in_skills_only": False,
        "project_points": [],
        "resume_match_status": "not_found",
    }

    # If AI is active and requested or custom technology:
    if providers and (force_ai or not is_curated or (resume_text and len(resume_text) > 100)):
        try:
            raw_cards = _generate_custom_cards_via_ai(canonical_name, target_role, resume_text, usage_info=usage_info)
        except Exception:
            raw_cards = []

    # Fallback to curated deck if available, else domain-aware deterministic
    if not raw_cards or len(raw_cards) < 4:
        if is_curated:
            raw_cards = [list(c) for c in CURATED_DECKS[norm_key]]
        else:
            raw_cards = _generate_deterministic_cards(canonical_name, target_role)

    # Apply tailoring
    tailored_cards = tailor_cheatsheet_for_resume(
        raw_cards,
        resume_text,
        target_role,
        canonical_name,
        usage_info=usage_info,
    )

    categories = ["All"] + list(dict.fromkeys(c[0] for c in tailored_cards if c[0]))

    return {
        "tech_name": canonical_name,
        "cards": tailored_cards,
        "categories": categories,
        "total_cards": len(tailored_cards),
        "target_role": target_role or "Software Engineer",
        "has_resume_tailoring": bool(resume_text or target_role),
        "used_in_resume": bool(usage_info.get("used_in_resume")),
        "resume_match_status": usage_info.get("resume_match_status", "not_found"),
        "deck_version": 2,
    }

# ---------------------------------------------------------------------------
# Standalone HTML Exporter (Matches User Attachment Exactly)
# ---------------------------------------------------------------------------
def build_standalone_cheatsheet_html(
    tech_name: str,
    cards: List[List[str]],
    target_role: str = "",
) -> str:
    """
    Produces a self-contained, offline-compatible HTML interview cheat sheet
    identical to the user's provided example file with WCAG AAA accessibility.
    """
    cards_json = json.dumps(cards)
    role_sub = f"Tailored for {target_role} interviews." if target_role else ""

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{tech_name} interview cheatsheet</title>
<style>
:root{{--bg:#f8fafc;--card:#ffffff;--ink:#0f172a;--mute:#334155;--line:#e2e8f0;--ac:#0f172a;--onac:#f8fafc;--acs:#f1f5f9;--cb:#0f172a;--cf:#f8fafc;--tip:#f1f5f9;--tl:#334155;box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}
@media(prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#090d16;--card:#0f172a;--ink:#f8fafc;--mute:#cbd5e1;--line:#1e293b;--ac:#f8fafc;--onac:#090d16;--acs:#141d2e;--cb:#050811;--cf:#e2e8f0;--tip:#141d2e;--tl:#cbd5e1}}}}
:root[data-theme="dark"]{{--bg:#090d16;--card:#0f172a;--ink:#f8fafc;--mute:#cbd5e1;--line:#1e293b;--ac:#f8fafc;--onac:#090d16;--acs:#141d2e;--cb:#050811;--cf:#e2e8f0;--tip:#141d2e;--tl:#cbd5e1}}
*{{box-sizing:border-box}}html{{scroll-padding-top:env(safe-area-inset-top,0px)}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
body::before{{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);background:var(--card);z-index:10}}
header{{position:sticky;top:env(safe-area-inset-top,0px);z-index:9;background:var(--card);border-bottom:1px solid var(--line);padding:14px 16px 10px}}
.w{{max-width:1100px;margin:0 auto}}
h1{{margin:0;font:700 1.5rem/1.2 Georgia,"Times New Roman",serif}}
.sub{{margin:2px 0 0;color:var(--mute);font-size:.9rem}}
.row{{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;align-items:center}}
input{{flex:1 1 220px;padding:9px 12px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);font:inherit}}
button{{font:inherit;cursor:pointer;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:8px;padding:7px 11px}}
button:hover{{border-color:var(--ac)}}:focus-visible{{outline:2px solid var(--ac);outline-offset:2px}}
.bar{{height:4px;background:var(--line);border-radius:2px;margin-top:10px}}.bar i{{display:block;height:100%;width:0;background:var(--ac);border-radius:2px;transition:width .3s}}
.chips{{display:flex;gap:6px;overflow-x:auto;padding:12px 0 2px}}
.ch{{border-radius:99px;white-space:nowrap;padding:5px 12px}}.ch.on{{background:var(--ac);border-color:var(--ac);color:var(--onac)}}
main{{padding:14px 16px 40px}}
#g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,420px),1fr));gap:12px;align-items:start}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;min-width:0}}
.card.done{{border-left:4px solid var(--ac)}}
summary{{cursor:pointer;padding:12px 14px;display:flex;gap:10px;align-items:center;list-style:none}}
summary::-webkit-details-marker{{display:none}}
summary::after{{content:"+";margin-left:auto;color:var(--ac);font-size:1.3rem;line-height:1}}
details[open] summary::after{{content:"\\2013"}}
.tg{{font-size:.75rem;background:var(--acs);color:var(--ac);padding:2px 8px;border-radius:99px;white-space:nowrap}}
.bd{{padding:12px 14px 14px;display:flex;flex-direction:column;gap:10px;border-top:1px solid var(--line)}}
.sec{{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:10px 12px}}
.sec-lbl{{display:block;font-size:.72rem;font-weight:800;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}}
.sec-def{{border-left:3.5px solid var(--mute)}}.lbl-def{{color:var(--mute)}}
.sec-project{{background:var(--acs);border:1px solid var(--line);border-left:4px solid var(--ac)}}.lbl-project{{color:var(--ac)}}
.cw{{position:relative;margin:0}}
pre{{margin:0;background:var(--cb);color:var(--cf);padding:12px;border-radius:8px;overflow-x:auto;font:12.5px/1.5 ui-monospace,Menlo,Consolas,monospace}}
.cp{{position:absolute;right:6px;top:6px;font-size:.75rem;padding:2px 8px}}
.tip{{background:var(--tip);border:1px solid var(--line);border-left:4px solid var(--tl);padding:10px 12px;border-radius:8px}}.lbl-tip{{color:var(--tl)}}
.dn{{margin-top:4px;font-size:.85rem}}.done .dn{{background:var(--acs);color:var(--ac)}}
#E{{text-align:center;color:var(--mute)}}
@media(prefers-reduced-motion:reduce){{*{{transition:none!important}}}}
</style></head><body>
<header><div class="w">
<h1>{tech_name} interview cheatsheet</h1>
<p class="sub" id="sub">{role_sub}</p>
<div class="row"><input id="S" type="search" placeholder="Search topics, e.g. architecture, scaling (press /)" aria-label="Search">
<button id="ea">Expand all</button><button id="ca">Collapse all</button><button id="rn">Random card</button><button id="th">Theme</button></div>
<div class="row" style="margin-top:8px"><span id="pt" class="sub"></span></div><div class="bar"><i id="pb"></i></div>
<div class="chips" id="chips"></div></div></header>
<main><div class="w"><div id="g"></div><p id="E" hidden>No match. Try another keyword or clear the filter.</p></div></main>
<script>
const D={cards_json};
const $=id=>document.getElementById(id),esc=s=>(s||'').replace(/[&<>]/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[m]));
const g=$('g');let cat='All',q='';
$('sub').textContent=D.length+' cards. ' + ($('sub').textContent || 'Tap a card to open it: interview answer, example, use case and tip.');
g.innerHTML=D.map(r=>`<details class="card" data-c="${{esc(r[0])}}"><summary><span class="tg">${{esc(r[0])}}</span><b>${{esc(r[1])}}</b></summary><div class="bd">${{r[2]?`<div class="sec sec-def"><span class="sec-lbl lbl-def">Standard Definition</span>${{esc(r[2])}}</div>`:''}}${{r[4]?`<div class="sec sec-project"><span class="sec-lbl lbl-project">How I Used This In My Work Experience / Personal Project</span>${{esc(r[4])}}</div>`:''}}${{r[3]?`<div class="cw"><span class="sec-lbl" style="color:var(--mute);margin:0 0 6px 2px;">Production Code &amp; Syntax Example</span><button class="cp">Copy</button><pre><code>${{esc(r[3])}}</code></pre></div>`:''}}${{r[5]?`<div class="tip"><span class="sec-lbl lbl-tip">Interview Pro Tip &amp; Gotchas</span>${{esc(r[5])}}</div>`:''}}<button class="dn">Mark as revised</button></div></details>`).join('');
const cards=()=>[...document.querySelectorAll('.card')],vis=()=>cards().filter(c=>!c.hidden);
const C=['All',...new Set(D.map(r=>r[0]))];
$('chips').innerHTML=C.map((c,i)=>`<button class="ch${{i?'':' on'}}">${{esc(c)}}</button>`).join('');
function f(){{let n=0;cards().forEach(c=>{{const ok=(cat=='All'||c.dataset.c==cat)&&c.textContent.toLowerCase().includes(q);c.hidden=!ok;n+=ok;if(ok&&q.length>1)c.open=true}});$('E').hidden=n>0}}
const p=()=>{{const d=document.querySelectorAll('.done').length;$('pt').textContent='Revised '+d+' of '+D.length;$('pb').style.width=d/D.length*100+'%'}};
$('S').oninput=e=>{{q=e.target.value.toLowerCase().trim();f()}};
$('chips').onclick=e=>{{const b=e.target.closest('.ch');if(!b)return;cat=b.textContent;document.querySelectorAll('.ch').forEach(x=>x.classList.toggle('on',x==b));f()}};
$('ea').onclick=()=>vis().forEach(c=>c.open=true);
$('ca').onclick=()=>cards().forEach(c=>c.open=false);
$('rn').onclick=()=>{{const v=vis();if(!v.length)return;const c=v[Math.random()*v.length|0];v.forEach(x=>x.open=false);c.open=true;c.scrollIntoView({{block:'center'}})}};
$('th').onclick=()=>{{const r=document.documentElement,d=r.dataset.theme?r.dataset.theme=='dark':matchMedia('(prefers-color-scheme:dark)').matches;r.dataset.theme=d?'light':'dark'}};
g.onclick=async e=>{{const t=e.target;
if(t.classList.contains('cp')){{try{{await navigator.clipboard.writeText(t.nextElementSibling.textContent);t.textContent='Copied'}}catch{{t.textContent='Select and copy'}}setTimeout(()=>t.textContent='Copy',1400)}}
if(t.classList.contains('dn')){{const c=t.closest('.card');c.classList.toggle('done');t.textContent=c.classList.contains('done')?'Revised':'Mark as revised';p()}}}};
onkeydown=e=>{{if(e.key=='/'&&document.activeElement!=$('S')){{e.preventDefault();$('S').focus()}}}};
p();
</script></body></html>"""
