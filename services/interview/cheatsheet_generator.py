"""
Technology Interview Cheat Sheet Generator for ResuMate Mock Interview.
Generates interactive, resume-tailored technical interview cheat sheets
with category filters, answers, code snippets, real-world use cases,
interview tips, and revision tracking.
"""

import re
import json
import os
from typing import Any, Dict, List, Optional
from openai import OpenAI

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
    "python": [
        [
            "Basics",
            "Memory Management & Garbage Collection",
            "Python manages memory through reference counting as its primary mechanism, complemented by a cyclic garbage collector that detects reference cycles in generation 0, 1, and 2. Objects with zero references are deallocated immediately.",
            "import sys, gc\n\nx = [1, 2, 3]\nprint(sys.getrefcount(x)) # reference count check\ngc.collect() # manually trigger cycle detection",
            "Debugging memory leaks in long-running services and data processing pipelines.",
            "Reference counting cannot reclaim objects pointing to each other (reference cycles); the generational cyclic GC runs periodically to break these cycles.",
        ],
        [
            "Concurrency",
            "The Global Interpreter Lock (GIL)",
            "The GIL is a mutex that prevents multiple native threads from executing Python bytecodes simultaneously within a single CPython process. For CPU-bound tasks, multithreading does not achieve parallelism; multiprocessing or native C extensions must be used. For I/O-bound tasks, asyncio or threading release the GIL during I/O operations.",
            "import multiprocessing\n\ndef compute(chunk):\n    return sum(x * x for x in chunk)\n\nif __name__ == '__main__':\n    with multiprocessing.Pool() as pool:\n        results = pool.map(compute, data_chunks)",
            "Designing high-throughput backend services and parallel batch processing.",
            "Python 3.13 introduces experimental free-threaded mode (PEP 703) to disable the GIL. Always distinguish between I/O concurrency (threads/asyncio) and CPU parallelism (multiprocessing).",
        ],
        [
            "Advanced",
            "Generators & Iterators",
            "A generator is a function that produces a sequence of values lazily using the yield statement rather than returning an entire collection at once. This achieves O(1) memory complexity when streaming large datasets or files.",
            "def read_large_file(file_path):\n    with open(file_path, 'r') as f:\n        for line in f:\n            yield line.strip()\n\nfor record in read_large_file('big_data.csv'):\n    process(record)",
            "Processing gigabyte-scale logs, streaming ETL pipelines, and infinite data streams.",
            "Generators implement the iterator protocol (__iter__ and __next__). Generator expressions (x for x in data) avoid allocating memory for intermediate lists.",
        ],
        [
            "Advanced",
            "Decorators & functools.wraps",
            "A decorator is a higher-order function that takes another function as an argument, extends or modifies its behavior, and returns the modified function. Using functools.wraps preserves the original function's name, docstring, and signature.",
            "from functools import wraps\nimport time\n\ndef timing_decorator(func):\n    @wraps(func)\n    def wrapper(*args, **kwargs):\n        start = time.perf_counter()\n        result = func(*args, **kwargs)\n        print(f\"{func.__name__} took {time.perf_counter() - start:.4f}s\")\n        return result\n    return wrapper",
            "Cross-cutting concerns: logging, authentication checks, caching, and rate limiting.",
            "Always include @wraps(func) inside custom decorators to prevent losing introspection attributes needed by testing tools and documentation generators.",
        ],
        [
            "Performance",
            "Data Structure Complexities",
            "Lists in Python are dynamic arrays with O(1) random access and append, but O(n) insert and delete at the front. Dictionaries and sets use hash tables with O(1) average lookup, insertion, and deletion. Collections.deque provides an O(1) double-ended queue.",
            "from collections import deque\n\nq = deque(maxlen=100)\nq.append(1)        # O(1)\nq.popleft()        # O(1) vs list.pop(0) which is O(n)",
            "Optimizing hot loops and selecting appropriate structures for algorithms.",
            "In Python 3.7+, standard dictionaries preserve insertion order. When maintaining frequency counts, collections.Counter is cleaner and faster.",
        ],
        [
            "Q&A",
            "Mutable vs Immutable Defaults in Functions",
            "Default arguments in Python are evaluated once when the function is defined, not each time it is called. Using a mutable object like a list or dictionary as a default causes the same object to be shared across all invocations.",
            "def append_item(val, target=None):\n    if target is None:\n        target = []\n    target.append(val)\n    return target",
            "Preventing subtle state leakage bugs in shared utility functions.",
            "Always use None as the default value for mutable arguments and instantiate the object inside the function body.",
        ],
    ],
    "postgresql": [
        [
            "Architecture",
            "ACID & Transaction Isolation Levels",
            "PostgreSQL implements ACID compliance through Write-Ahead Logging (WAL) and Multi-Version Concurrency Control (MVCC). It supports four isolation levels: Read Committed (default), Repeatable Read, and Serializable, preventing dirty reads, non-repeatable reads, and phantom reads.",
            "-- Setting transaction isolation level\nBEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;\nSELECT balance FROM accounts WHERE id = 1;\n-- updates and balance check\nCOMMIT;",
            "Financial transactions, inventory reservations, and payment processing.",
            "PostgreSQL's default Read Committed level avoids dirty reads, but non-repeatable reads can occur if another transaction commits mid-way.",
        ],
        [
            "Performance",
            "Indexing Strategies (B-Tree, GIN, GiST)",
            "PostgreSQL offers multiple index types: B-Tree for standard equality and range queries, GIN for full-text search and JSONB containment (@>), GiST for geometric and range types, and BRIN for naturally ordered massive sequential tables.",
            "-- Standard B-Tree index\nCREATE INDEX idx_users_email ON users(email);\n\n-- GIN index for JSONB\nCREATE INDEX idx_audit_meta ON audit_logs USING GIN(metadata);",
            "Optimizing complex queries, JSON document lookups, and geospatial calculations.",
            "Use partial indexes (WHERE active = true) to index only rows of interest, drastically shrinking index size and maintenance overhead.",
        ],
        [
            "Performance",
            "EXPLAIN (ANALYZE, BUFFERS)",
            "EXPLAIN ANALYZE runs the query and displays the actual execution plan, node timings, and row counts alongside the planner's estimates. Adding BUFFERS reveals shared hit and read counts, showing cache utilization.",
            "EXPLAIN (ANALYZE, BUFFERS, VERBOSE)\nSELECT * FROM orders\nWHERE customer_id = 42\nORDER BY created_at DESC LIMIT 20;",
            "Diagnosing slow database queries, identifying full table scans, and verifying index usage.",
            "Watch out for large discrepancies between estimated rows and actual rows; this indicates outdated statistics that can be resolved with ANALYZE tablename.",
        ],
        [
            "Operations",
            "VACUUM and MVCC Bloat",
            "PostgreSQL's MVCC creates a new row version (tuple) on every UPDATE and marks deleted rows as dead. The autovacuum daemon runs in the background to clean dead tuples and freeze transaction IDs to prevent wraparound.",
            "-- Check table bloat and dead tuple count\nSELECT relname, n_dead_tup, n_live_tup\nFROM pg_stat_user_tables\nORDER BY n_dead_tup DESC;",
            "Preventing disk space exhaustion and query degradation in write-heavy workloads.",
            "Never disable autovacuum. If write volume is extreme, tune autovacuum_vacuum_scale_factor and autovacuum_vacuum_cost_limit per table.",
        ],
        [
            "Q&A",
            "Connection Pooling: PgBouncer vs App Pooling",
            "Each PostgreSQL backend connection consumes memory (typically 5-10MB) and fork overhead. PgBouncer provides lightweight connection pooling outside the application, supporting session, transaction, or statement pooling to handle thousands of concurrent client connections.",
            "# pgbouncer.ini configuration snippet\n[databases]\ncareer_db = host=127.0.0.1 port=5432 dbname=career_db\n\n[pgbouncer]\npool_mode = transaction\nmax_client_conn = 1000\ndefault_pool_size = 25",
            "Preventing serverless function connection starvation (AWS Lambda, Vercel).",
            "Transaction pooling is most common for microservices, but prepared statements and temporary tables are reset between transactions unless using PgBouncer 1.21+ protocol-level prepared statements.",
        ],
    ],
    "docker": [
        [
            "Basics",
            "Containers vs Virtual Machines",
            "A virtual machine runs a complete guest operating system on top of a hypervisor, consuming significant memory and boot time. A Docker container shares the host OS kernel and isolates processes using Linux namespaces (PID, NET, MNT) and cgroups for resource limits, starting in milliseconds.",
            "# Inspect container resource limits\ndocker run -d --name app-worker \\\n  --cpus=\"1.5\" --memory=\"1g\" \\\n  -p 8000:8000 my-image:latest",
            "Deploying portable microservices across local development and production clusters.",
            "Namespaces provide isolation (what the process can see); cgroups enforce resource restrictions (what the process can use).",
        ],
        [
            "Best Practices",
            "Multi-Stage Docker Builds",
            "Multi-stage builds allow separating build-time dependencies (compilers, build tools, dev libraries) from the final minimal runtime image. This dramatically shrinks image size and reduces attack surface.",
            "FROM python:3.11-slim AS builder\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir --user -r requirements.txt\n\nFROM python:3.11-slim\nWORKDIR /app\nCOPY --from=builder /root/.local /root/.local\nCOPY . .\nENV PATH=/root/.local/bin:$PATH\nCMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\"]",
            "Production Docker images in CI/CD pipelines.",
            "Order commands from least frequently changed (OS updates, pip install) to most frequently changed (COPY code) to maximize Docker layer cache hits.",
        ],
        [
            "Security",
            "Non-root Containers & Security Hardening",
            "By default, containers execute as the root user. If a process escape vulnerability occurs, the attacker gains host root access. In production, always create and switch to a dedicated non-root user, and use read-only filesystems when possible.",
            "RUN addgroup --system appgroup && adduser --system --group appuser\nUSER appuser\nEXPOSE 8080\nCMD [\"python\", \"server.py\"]",
            "Hardened enterprise deployment environments and compliance standards.",
            "In Kubernetes, enforce securityContext: runAsNonRoot: true and drop all capabilities except necessary ones.",
        ],
        [
            "Q&A",
            "CMD vs ENTRYPOINT",
            "ENTRYPOINT specifies the default executable that will always be invoked when the container runs. CMD provides default arguments that can be easily overridden by passing arguments after docker run.",
            "ENTRYPOINT [\"python\", \"main.py\"]\nCMD [\"--port\", \"8000\"]\n# docker run my-img --port 9000 overrides CMD but keeps ENTRYPOINT",
            "Creating purpose-built CLI tool containers and microservice runners.",
            "Prefer the exec format ([\"executable\", \"param\"]) over shell format to ensure SIGTERM signals propagate directly to your application for graceful shutdown.",
        ],
    ],
    "react": [
        [
            "Core",
            "React 18 Concurrent Features & Fiber",
            "React Fiber is a rewrite of the reconciliation algorithm that models rendering as a virtual stack frame. It enables Concurrent React, allowing React to pause, resume, and abandon render work to keep the main thread responsive during expensive renders.",
            "import { useTransition, useState } from 'react';\n\nfunction SearchResults() {\n  const [isPending, startTransition] = useTransition();\n  const [query, setQuery] = useState('');\n\n  function handleChange(e) {\n    // Urgent update (input field typing)\n    setQuery(e.target.value);\n    // Non-urgent update (filtering list)\n    startTransition(() => {\n      filterLargeList(e.target.value);\n    });\n  }",
            "Maintaining 60 FPS UI responsiveness while rendering large lists or complex charts.",
            "useTransition marks state updates as non-urgent transitions; useDeferredValue defers re-rendering non-critical child components.",
        ],
        [
            "Performance",
            "useMemo, useCallback & React.memo",
            "useMemo caches the result of an expensive calculation between renders. useCallback caches a function definition to prevent child component re-renders when passing callbacks. React.memo wraps a component to skip re-rendering if its props are shallowly equal.",
            "import React, { useMemo, useCallback } from 'react';\n\nconst MemoizedRow = React.memo(({ item, onSelect }) => {\n  return <button onClick={() => onSelect(item.id)}>{item.name}</button>;\n});\n\nfunction List({ items }) {\n  const handleSelect = useCallback((id) => console.log(id), []);\n  return items.map(item => <MemoizedRow key={item.id} item={item} onSelect={handleSelect} />);\n}",
            "Preventing unnecessary re-renders in large lists and data grids.",
            "Do not prematurely wrap every function in useCallback; the overhead of allocation and dependency comparison can exceed the cost of re-rendering small components.",
        ],
        [
            "State",
            "State Colocation & Context Optimization",
            "State colocation means keeping state as close to where it is used as possible. When global state is necessary, React Context can trigger re-renders in all consumers whenever the value changes. Splitting contexts into State and Dispatch avoids re-renders.",
            "const StateContext = createContext();\nconst DispatchContext = createContext();\n\nfunction UserProvider({ children }) {\n  const [state, dispatch] = useReducer(userReducer, initial);\n  return (\n    <DispatchContext.Provider value={dispatch}>\n      <StateContext.Provider value={state}>{children}</StateContext.Provider>\n    </DispatchContext.Provider>\n  );\n}",
            "Structuring scalable frontend applications without monolithic rerender waterfalls.",
            "Components that only trigger actions should consume DispatchContext, remaining unaffected when state values mutate.",
        ],
        [
            "Q&A",
            "Server-Side Rendering (SSR) vs Client-Side (CSR) vs Static (SSG)",
            "CSR renders everything in the user's browser, leading to slower First Contentful Paint (FCP). SSR renders HTML on the server on each request, improving SEO and initial render. SSG pre-renders HTML at build time for instant CDN delivery. Next.js combines these with Incremental Static Regeneration (ISR).",
            "",
            "Architectural decisions for e-commerce, dashboards, and content platforms.",
            "Always link choice to business goals: SSG/ISR for marketing & blogs; SSR for authenticated personalized dashboards; CSR for interactive canvas apps.",
        ],
    ],
    "redis": [
        [
            "Architecture",
            "Single-Threaded Event Loop & In-Memory Speed",
            "Redis operates entirely in RAM and uses a single-threaded multiplexed event loop (epoll/kqueue) to process commands sequentially, eliminating lock contention and thread context switching. In Redis 6+, I/O threading handles socket reading and writing concurrently while command execution remains atomic.",
            "# Connecting and atomic operations\nredis-cli\nSETNX resource_lock 1\nEXPIRE resource_lock 10",
            "High-speed caching, distributed rate limiting, and real-time leaderboards.",
            "Because Redis is single-threaded for command execution, avoid commands with O(n) complexity like KEYS * on production instances; use SCAN instead.",
        ],
        [
            "Patterns",
            "Caching Strategies: Cache-Aside vs Write-Through",
            "In Cache-Aside, the application queries Redis first; if a miss occurs, it loads data from the database, writes it to Redis with a TTL, and returns. In Write-Through, the application writes to the cache and database simultaneously.",
            "def get_user_profile(user_id):\n    cached = redis_client.get(f\"user:{user_id}\")\n    if cached:\n        return json.loads(cached)\n    user = db.query_user(user_id)\n    redis_client.setex(f\"user:{user_id}\", 3600, json.dumps(user))\n    return user",
            "Sub-10ms profile fetching in high-traffic APIs.",
            "Always configure a reasonable TTL (Time-To-Live) to avoid stale data accumulation, and handle the Thundering Herd / Cache Stampede problem using mutexes or probabilistic early expiration.",
        ],
        [
            "Persistence",
            "RDB Snapshots vs AOF (Append-Only File)",
            "Redis offers two persistence options: RDB creates point-in-time binary snapshots on disk at configured intervals, while AOF logs every write command sequentially. Most production setups use both: AOF with appendfsync everysec for minimal data loss, and RDB for rapid disaster recovery.",
            "# redis.conf persistence settings\nsave 900 1\nappendonly yes\nappendfsync everysec",
            "Balancing durability vs throughput in mission-critical applications.",
            "AOF can be rewritten in the background (BGREWRITEAOF) to compress redundant operations without downtime.",
        ],
    ],
}

# ---------------------------------------------------------------------------
# Technology Extraction from Resume
# ---------------------------------------------------------------------------
def extract_technologies_from_resume(resume_text: str, report: Optional[Dict[str, Any]] = None) -> List[str]:
    """
    Extracts all recognized technologies from the candidate's resume text and report.
    Returns prioritized canonical technology names.
    """
    detected: List[str] = []
    seen = set()

    full_corpus = (resume_text or "").lower()
    if report and isinstance(report, dict):
        full_corpus += " " + json.dumps(report).lower()

    # Match against canonical registry
    for tech_id, meta in TECH_REGISTRY.items():
        canonical = meta["canonical"]
        aliases = meta.get("aliases", [canonical.lower()])
        for alias in aliases:
            pattern = r"(?:\b|_)" + re.escape(alias) + r"(?:\b|_)"
            if re.search(pattern, full_corpus):
                if canonical not in seen:
                    seen.add(canonical)
                    detected.append(canonical)
                break

    # If no resume skills detected, fallback to popular full-stack stack
    if not detected:
        return ["FastAPI", "Python", "PostgreSQL", "Docker", "React"]

    return detected

# ---------------------------------------------------------------------------
# Dynamic AI Generator for Custom Technologies
# ---------------------------------------------------------------------------
def _generate_custom_cards_via_ai(tech_name: str, target_role: str = "", resume_context: str = "") -> List[List[str]]:
    """
    Invokes external LLM to generate 12-16 structured interview cards for any custom technology.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "dummy":
        return _generate_deterministic_cards(tech_name, target_role)

    prompt = f"""
You are an expert technical interviewer preparing an interview cheat sheet for: {tech_name}.
Candidate target role: {target_role or "Software Engineer"}.
Resume context snippet: {resume_context[:600] if resume_context else "General candidate"}.

Create 12 to 16 comprehensive, high-yield interview cards for {tech_name}.
Categories to include: Basics, Architecture, Performance, Security, Testing & Best Practices, Common Interview Q&A.

Return ONLY a valid JSON array of cards where each card is a 6-element array:
[
  "Category",
  "Topic Title",
  "Standard Definition: A clear, authoritative technical definition explaining what the feature is and how it works",
  "Code example (or clean configuration snippet, or empty string if not applicable)",
  "How I used this in my work experience / personal project: Concrete production use case with architectural details and metrics",
  "Interview tip / common gotcha to watch out for: How to answer out loud and pitfalls to avoid"
]

Strict rules:
- Return ONLY the JSON array, no markdown fences, no surrounding commentary.
- Every card must have high technical accuracy and concrete talking points.
"""
    try:
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2500,
        )
        content = response.choices[0].message.content or ""
        cleaned = content.replace("```json", "").replace("```", "").strip()
        if "[" in cleaned and "]" in cleaned:
            cleaned = cleaned[cleaned.find("[") : cleaned.rfind("]") + 1]
        data = json.loads(cleaned)
        if isinstance(data, list) and len(data) >= 4 and all(isinstance(c, list) and len(c) >= 6 for c in data):
            return data
    except Exception:
        pass

    return _generate_deterministic_cards(tech_name, target_role)


def _generate_deterministic_cards(tech_name: str, target_role: str = "") -> List[List[str]]:
    """
    Deterministic offline fallback generator for any technology.
    Produces rich, structured cards covering all critical interview angles.
    """
    title_tech = tech_name.strip().title()
    role = target_role or "Software Engineer"

    return [
        [
            "Basics",
            f"What is {title_tech} and when to use it",
            f"{title_tech} is a critical industry tool designed for high reliability and scalability. In an interview, I explain that we adopt {title_tech} when building production systems that require clear separation of concerns, fast execution, and maintainable architecture. For our {role} responsibilities, it provides standardized patterns that reduce system downtime.",
            f"# Core usage pattern for {title_tech}\n# Initialize and configure runtime parameters\nsetup_{tech_name.lower()} = True",
            f"Standardizing backend microservices and reliable infrastructure in {role} workflows.",
            f"Always begin your answer by stating the exact problem {title_tech} solves before diving into internal implementation details.",
        ],
        [
            "Architecture",
            f"Core Architecture & Internals of {title_tech}",
            f"Under the hood, {title_tech} is structured around modular components that isolate execution, state handling, and resource pooling. It minimizes operational overhead by leveraging efficient communication protocols and predictable lifecycle events.",
            "",
            f"Deploying scalable components within high-throughput distributed systems.",
            "Interviewers want to hear about trade-offs: what {title_tech} does well versus where it might introduce unnecessary complexity.",
        ],
        [
            "Performance",
            f"Performance Optimization & Bottlenecks in {title_tech}",
            f"To optimize {title_tech} in production, I focus on connection pooling, minimizing serialization overhead, and profiling critical paths. When bottlenecks arise, we monitor CPU saturation, memory utilization, and network I/O latency to identify slow queries or blocking calls.",
            f"# Performance profiling checklist\n# 1. Check thread/worker allocation\n# 2. Monitor I/O latency and buffer sizes",
            "Eliminating tail latencies and handling peak traffic spikes gracefully.",
            "Quantify your answers: explain how profiling {title_tech} reduced latency by 30-50% in prior production deployments.",
        ],
        [
            "Security",
            f"Security Best Practices with {title_tech}",
            f"Security in {title_tech} requires strict adherence to the principle of least privilege, input sanitization to prevent injection vulnerabilities, secure credential rotation via environment variables or secret managers, and continuous vulnerability scanning.",
            "",
            "Securing enterprise deployments and adhering to SOC2 / ISO compliance.",
            "Never hardcode tokens or credentials in codebases; mention secret management tools like AWS Secrets Manager or HashiCorp Vault.",
        ],
        [
            "Testing",
            f"Testing & CI/CD Verification for {title_tech}",
            f"I test {title_tech} components by isolating business logic with unit tests, mocking external boundaries, and running comprehensive end-to-end integration tests in CI/CD before any production deployment.",
            f"def test_{tech_name.lower()}_integration():\n    # Arrange: prepare mock input\n    # Act: execute pipeline\n    # Assert: verify deterministic outcome\n    assert True",
            "Automated test coverage in fast deployment cycles.",
            "Mention dependency injection and test fixtures; interviewers appreciate candidates who prioritize maintainable, flaky-free test suites.",
        ],
        [
            "Q&A",
            f"Common Pitfalls and Gotchas in {title_tech}",
            f"A common trap with {title_tech} is failing to account for unhandled edge cases, connection leaks, or misconfigured timeout thresholds. In production, every network call and resource allocation should carry explicit timeouts and retry backoff policies.",
            "",
            "Building resilient failure recovery mechanisms.",
            "Admitting a past bug or gotcha you resolved with {title_tech} demonstrates senior-level maturity and hands-on experience.",
        ],
    ]

# ---------------------------------------------------------------------------
# Tailoring Cards with Resume Context & Project Bullet Points
# ---------------------------------------------------------------------------
def extract_project_talking_points_for_tech(resume_context: str, tech_name: str) -> List[Dict[str, str]]:
    """
    Extracts candidate projects, work experiences, metrics, and bullet points from
    the resume that utilize or relate to the given technology.
    """
    if not resume_context or not tech_name:
        return []

    tech_lower = tech_name.lower().strip()
    clean_text = resume_context.replace(r"\textbf{", "").replace("}", "").replace(r"\resumeItem{", "")
    clean_text = clean_text.replace(r"\textit{", "").replace(r"\noindent", "").replace(r"\section*{", "")
    clean_text = clean_text.replace(r"\small", "").replace(r"\\", "\n")

    lines = [ln.strip() for ln in clean_text.splitlines() if ln.strip()]
    matches = []
    current_context = ""

    in_skills_section = False
    for line in lines:
        lower = line.lower()
        if "technical skills" in lower or ("skills" in lower and len(line) < 30):
            in_skills_section = True
            continue
        if any(sec in lower for sec in ["professional experience", "experience", "key projects", "projects", "employment"]):
            in_skills_section = False

        if in_skills_section:
            continue

        if any(term in lower for term in ["capgemini", "associate consultant"]):
            current_context = "Capgemini Data Engineering"
        elif "tech solutions lab" in lower:
            current_context = "Tech Solutions Lab"
        elif "careerai" in lower or "career intelligence" in lower:
            current_context = "CareerAI Platform Project"
        elif "lakehouse" in lower or "streaming pipeline" in lower:
            current_context = "Enterprise Lakehouse Pipeline"
        elif line.startswith(("#", "**", "Project:", "Role:")) or (" – " in line and len(line) < 80 and not line.startswith("-")):
            current_context = re.sub(r"[\#\*\\]", "", line).strip()[:50]

        if tech_lower in lower:
            clean_line = re.sub(r"\\[a-zA-Z]+\*?|\{|\}", "", line)
            clean_line = clean_line.strip(" *#-\t\n\r")
            words = clean_line.split()
            if len(words) >= 5 and not any(h in lower for h in ["languages:", "frameworks:", "tools:", "platforms:"]):
                matches.append({"context": current_context or "Resume Project", "point": clean_line})

    seen = set()
    deduped = []
    for m in matches:
        if m["point"] not in seen:
            seen.add(m["point"])
            deduped.append(m)

    return deduped


def tailor_cheatsheet_for_resume(
    cards: List[List[str]],
    resume_context: str = "",
    target_role: str = "",
    tech_name: str = "",
) -> List[List[str]]:
    """
    Enriches cheat sheet cards with personalized candidate talking points
    tailored to the user's specific resume projects and target role.
    """
    if not resume_context and not target_role:
        return cards

    project_points = extract_project_talking_points_for_tech(resume_context, tech_name)
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
        elif resume_context:
            c_use = f"In your {role_mention} portfolio projects: Applied {c_title} in production workflows to eliminate bottlenecks, ensure high throughput, and maintain resilient data consistency."
            if idx == 0 and target_role:
                c_tip = f"Tailored for your {role_mention} interviews: Lead with measurable outcomes from your projects when explaining this concept. " + c_tip
            elif c_cat == "Q&A":
                c_tip = f"Resume anchor: Connect this question to the architectural decisions you made in your resume projects. " + c_tip
        elif target_role:
            c_use = f"Recommended application for {role_mention}: Implemented {c_title} in production services to eliminate single points of failure and streamline API operations."
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
) -> Dict[str, Any]:
    """
    Returns full cheat sheet payload for a technology, incorporating
    curated high-yield cards or dynamic AI generation with resume tailoring.
    """
    norm_key = re.sub(r"[^a-zA-Z0-9]+", "", tech_name.lower().strip())
    canonical_name = tech_name.strip()

    # Check canonical registry
    for k, meta in TECH_REGISTRY.items():
        if norm_key == k or norm_key in [re.sub(r"[^a-zA-Z0-9]+", "", a) for a in meta.get("aliases", [])]:
            canonical_name = meta["canonical"]
            norm_key = k
            break

    # Load curated deck if available
    if norm_key in CURATED_DECKS:
        raw_cards = [list(c) for c in CURATED_DECKS[norm_key]]
    else:
        # Dynamically generate
        raw_cards = _generate_custom_cards_via_ai(canonical_name, target_role, resume_text)

    # Apply tailoring
    tailored_cards = tailor_cheatsheet_for_resume(raw_cards, resume_text, target_role, canonical_name)

    categories = ["All"] + list(dict.fromkeys(c[0] for c in tailored_cards if c[0]))

    return {
        "tech_name": canonical_name,
        "cards": tailored_cards,
        "categories": categories,
        "total_cards": len(tailored_cards),
        "target_role": target_role or "Software Engineer",
        "has_resume_tailoring": bool(resume_text or target_role),
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
