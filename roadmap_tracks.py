"""
Programmatic SEO Roadmap Tracks Data
Curated, high-intent career tracks designed for search engine indexing and user conversion.
"""

TRACKS_DATA = {
    "python-developer": {
        "slug": "python-developer",
        "role_name": "Python Developer",
        "h1_title": "Python Developer Roadmap 2026",
        "seo_title": "Python Developer Roadmap 2026: Skills, Milestones & Career Guide | ResuMate",
        "meta_desc": "Complete step-by-step 2026 roadmap for Python developers. Learn required skills, FastAPI, Django, PostgreSQL, system design, and interview expectations.",
        "tagline": "Master modern Python 3.12+, high-performance async APIs, database optimization, and cloud-native backend architectures.",
        "avg_salary": "$115,000 – $165,000 / yr",
        "est_time": "4 – 6 Months",
        "demand_level": "Very High 🔥",
        "overview": (
            "Python remains one of the most in-demand backend and data languages in 2026. "
            "Modern engineering teams look beyond syntax: hiring managers test your depth in async programming (asyncio), "
            "Pydantic v2 data validation, modern microservices with FastAPI and Django, database pooling with SQLAlchemy 2.0, "
            "and production containerization."
        ),
        "phases": [
            {
                "num": 1,
                "title": "Language Internals & Modern Python",
                "badge": "Phase 1 · Foundation",
                "summary": "Master Python 3.10+ idioms, memory management, and typing before touching frameworks.",
                "skills": [
                    {
                        "name": "Type Hints & Pydantic v2",
                        "desc": "Modern Python codebases rely on strict type safety with MyPy and runtime data validation via Pydantic.",
                        "tools": ["MyPy", "Pydantic v2", "typing module"],
                        "interview_tip": "Be prepared to explain the difference between static type checking and runtime validation."
                    },
                    {
                        "name": "Asyncio & Concurrency",
                        "desc": "Event loops, coroutines, tasks, and task groups (Python 3.11+) for high-throughput I/O.",
                        "tools": ["asyncio", "httpx", "aiofiles"],
                        "interview_tip": "Know the difference between CPU-bound (multiprocessing) and I/O-bound (asyncio) tasks."
                    },
                    {
                        "name": "Metaprogramming & Decorators",
                        "desc": "Writing reusable decorators with functools.wraps, understanding dunder methods and descriptors.",
                        "tools": ["functools", "contextlib", "inspect"],
                        "interview_tip": "Interviews frequently ask candidates to write a timing or caching decorator from scratch."
                    }
                ]
            },
            {
                "num": 2,
                "title": "Production Web Frameworks & APIs",
                "badge": "Phase 2 · Web Engineering",
                "summary": "Building scalable, documented REST and WebSocket APIs conforming to OpenAPI standards.",
                "skills": [
                    {
                        "name": "FastAPI & Dependency Injection",
                        "desc": "High-performance asynchronous REST endpoints, middleware pipelines, and structured dependency injection.",
                        "tools": ["FastAPI", "Starlette", "Uvicorn"],
                        "interview_tip": "Understand how FastAPI manages thread pools for synchronous routes versus native async routes."
                    },
                    {
                        "name": "Django & Django REST Framework",
                        "desc": "Full-featured monoliths, migrations, administrative tools, and robust ORM integration.",
                        "tools": ["Django 5", "DRF", "django-filter"],
                        "interview_tip": "Expect questions on solving N+1 query problems using select_related and prefetch_related."
                    },
                    {
                        "name": "Authentication & API Security",
                        "desc": "JWT access/refresh token rotation, OAuth2 password flows, rate limiting, and CORS.",
                        "tools": ["python-jose", "passlib", "slowapi"],
                        "interview_tip": "Explain how to securely store passwords using bcrypt and validate JWT expiry timestamps."
                    }
                ]
            },
            {
                "num": 3,
                "title": "Data Persistence & Caching",
                "badge": "Phase 3 · Data Tier",
                "summary": "Writing robust data layers with relational models, indexing strategies, and caching.",
                "skills": [
                    {
                        "name": "PostgreSQL & Advanced SQL",
                        "desc": "Complex joins, window functions, CTEs, transactions (ACID), and query planning with EXPLAIN ANALYZE.",
                        "tools": ["PostgreSQL", "pgvector", "psycopg3"],
                        "interview_tip": "Know how B-Tree indexes work and when composite indexes improve query performance."
                    },
                    {
                        "name": "SQLAlchemy 2.0 & Alembic",
                        "desc": "Declarative mapping, modern select() syntax, session lifecycles, and automated schema migrations.",
                        "tools": ["SQLAlchemy 2.0", "Alembic"],
                        "interview_tip": "Know how connection pooling avoids database socket exhaustion during peak load."
                    },
                    {
                        "name": "Redis In-Memory Caching",
                        "desc": "Cache-aside patterns, TTL expiration, distributed locking, and rate limiter storage.",
                        "tools": ["Redis", "redis-py"],
                        "interview_tip": "Be prepared to design a cache invalidation strategy for high-write endpoints."
                    }
                ]
            },
            {
                "num": 4,
                "title": "Asynchronous Workers & Distributed Systems",
                "badge": "Phase 4 · Scalability",
                "summary": "Offloading long-running jobs, sending notifications, and messaging between microservices.",
                "skills": [
                    {
                        "name": "Celery & Background Tasks",
                        "desc": "Distributed task queues, retry logic with exponential backoff, and task routing.",
                        "tools": ["Celery", "RabbitMQ", "Redis"],
                        "interview_tip": "Discuss how idempotency prevents duplicate task execution in at-least-once queues."
                    },
                    {
                        "name": "Event Streaming & Message Brokers",
                        "desc": "Publish/subscribe architectures and decoupling producer/consumer services.",
                        "tools": ["Kafka", "RabbitMQ", "AWS SQS"],
                        "interview_tip": "Explain the architectural trade-offs between a queue (RabbitMQ) and an event log (Kafka)."
                    }
                ]
            },
            {
                "num": 5,
                "title": "Testing, CI/CD & Cloud Deployment",
                "badge": "Phase 5 · Production Delivery",
                "summary": "Delivering reliable code through automated pipelines, Docker microcontainers, and cloud monitoring.",
                "skills": [
                    {
                        "name": "Automated Testing with Pytest",
                        "desc": "Unit tests, fixtures, mocking third-party APIs, and test coverage targets.",
                        "tools": ["Pytest", "pytest-asyncio", "unittest.mock"],
                        "interview_tip": "Highlight how fixtures provide deterministic database states before each test execution."
                    },
                    {
                        "name": "Docker & Multi-Stage Builds",
                        "desc": "Containerizing Python apps with slim Linux bases, non-root users, and minimal bundle sizes.",
                        "tools": ["Docker", "Docker Compose", "distroless"],
                        "interview_tip": "Know why multi-stage builds reduce image vulnerabilities and decrease deployment times."
                    },
                    {
                        "name": "Cloud & CI/CD Pipelines",
                        "desc": "Automated linting (Ruff), test runners in GitHub Actions, and deployments to AWS/Vercel.",
                        "tools": ["GitHub Actions", "AWS ECS", "Vercel", "Ruff"],
                        "interview_tip": "Be ready to explain how healthcheck endpoints (/healthz, /readyz) orchestrate zero-downtime rollouts."
                    }
                ]
            }
        ],
        "faqs": [
            {
                "q": "How long does it take to become a job-ready Python Developer in 2026?",
                "a": "With 15–20 hours per week of focused study and building real projects, most learners reach job readiness within 4 to 6 months."
            },
            {
                "q": "Should I learn FastAPI or Django first?",
                "a": "Learn FastAPI first if you are building modern REST APIs or AI application backends. Learn Django if you want to understand full-stack monolithic architectures and built-in ORM tooling."
            },
            {
                "q": "What is the most common reason candidates fail Python technical interviews?",
                "a": "Failing to explain database query optimization (e.g. N+1 queries in ORMs), lack of unit testing, and treating Python as single-threaded without understanding asyncio or multiprocessing."
            }
        ],
        "mindmap_root": {
            "name": "Python Developer",
            "children": [
                {
                    "name": "Core Language",
                    "children": [{"name": "Type Hints & Pydantic"}, {"name": "Asyncio & Tasks"}, {"name": "Decorators & Generators"}]
                },
                {
                    "name": "Web Frameworks",
                    "children": [{"name": "FastAPI"}, {"name": "Django REST"}, {"name": "OAuth2 & JWT"}]
                },
                {
                    "name": "Databases & ORM",
                    "children": [{"name": "PostgreSQL"}, {"name": "SQLAlchemy 2.0"}, {"name": "Redis Caching"}]
                },
                {
                    "name": "Async Systems",
                    "children": [{"name": "Celery Queues"}, {"name": "RabbitMQ / Kafka"}]
                },
                {
                    "name": "Testing & DevOps",
                    "children": [{"name": "Pytest"}, {"name": "Docker"}, {"name": "GitHub Actions"}]
                }
            ]
        }
    },

    "react-frontend-engineer": {
        "slug": "react-frontend-engineer",
        "role_name": "Frontend & React Engineer",
        "h1_title": "React & Frontend Engineer Roadmap 2026",
        "seo_title": "React & Frontend Engineer Roadmap 2026: Modern Web Skills & Path | ResuMate",
        "meta_desc": "Comprehensive 2026 guide and milestone roadmap for React and Frontend developers. Master Next.js App Router, TypeScript, Tailwind, and Core Web Vitals.",
        "tagline": "Build fast, accessible, and reactive web applications with React 19, Next.js, TypeScript, and state-of-the-art styling.",
        "avg_salary": "$110,000 – $160,000 / yr",
        "est_time": "4 – 5 Months",
        "demand_level": "Extremely High 🔥",
        "overview": (
            "Frontend engineering in 2026 has matured dramatically. Modern teams demand strong TypeScript proficiency, "
            "deep understanding of React Server Components (RSC), Next.js App Router, optimistic UI updates, "
            "and strict Core Web Vitals compliance (INP, LCP, CLS)."
        ),
        "phases": [
            {
                "num": 1,
                "title": "TypeScript & Modern JavaScript",
                "badge": "Phase 1 · Foundations",
                "summary": "Mastering modern ES2024 features and strict TypeScript type systems.",
                "skills": [
                    {
                        "name": "Strict TypeScript",
                        "desc": "Generics, utility types (Partial, Pick, Omit), discriminated unions, and strict null checking.",
                        "tools": ["TypeScript 5+", "tsc"],
                        "interview_tip": "Explain how discriminated unions prevent runtime bugs in API response handling."
                    },
                    {
                        "name": "Modern DOM & Async JS",
                        "desc": "Event delegation, bubbling, Promise.allSettled, Fetch API, and AbortController for request cancellation.",
                        "tools": ["AbortController", "Web APIs"],
                        "interview_tip": "Interviews often ask you to implement an auto-cancelling search input with AbortController."
                    }
                ]
            },
            {
                "num": 2,
                "title": "React 19 & Next.js Architecture",
                "badge": "Phase 2 · Framework Core",
                "summary": "Building modern full-stack web applications with React 19 and Next.js App Router.",
                "skills": [
                    {
                        "name": "React Server Components (RSC)",
                        "desc": "Understanding server-side rendering, streaming HTML with Suspense, and boundary separation.",
                        "tools": ["Next.js App Router", "React 19"],
                        "interview_tip": "Articulate clearly what code executes on the server vs what ships in the client bundle."
                    },
                    {
                        "name": "State Management & Server State",
                        "desc": "TanStack Query for server cache, Zustand for lightweight client state, and optimistic mutations.",
                        "tools": ["TanStack Query", "Zustand"],
                        "interview_tip": "Explain why server cache (TanStack Query) has largely replaced monolithic global stores like Redux."
                    },
                    {
                        "name": "Modern CSS & Tailwind UI",
                        "desc": "Tailwind CSS, CSS Grid, container queries, and headless UI accessibility primitives.",
                        "tools": ["Tailwind CSS", "shadcn/ui", "Radix UI"],
                        "interview_tip": "Discuss the performance and bundle size benefits of utility-first CSS over runtime CSS-in-JS."
                    }
                ]
            },
            {
                "num": 3,
                "title": "Performance & Web Vitals",
                "badge": "Phase 3 · Optimization",
                "summary": "Passing Google Core Web Vitals and eliminating re-render bottlenecks.",
                "skills": [
                    {
                        "name": "Interaction to Next Paint (INP) & LCP",
                        "desc": "Diagnosing main thread blockers, optimizing bundle splitting, and deferring non-critical scripts.",
                        "tools": ["Chrome DevTools", "Lighthouse", "Web Vitals API"],
                        "interview_tip": "Know how INP differs from FID and how to break long tasks using requestIdleCallback or setTimeout."
                    },
                    {
                        "name": "React Re-Render Optimization",
                        "desc": "Using React Compiler, memoization strategies, and moving state down to avoid cascade renders.",
                        "tools": ["React DevTools Profiler", "useMemo", "useCallback"],
                        "interview_tip": "Explain when memoization adds unnecessary overhead vs when it prevents expensive tree re-renders."
                    }
                ]
            },
            {
                "num": 4,
                "title": "Testing & Automated Quality",
                "badge": "Phase 4 · Reliability",
                "summary": "Unit and end-to-end testing user interactions across browsers.",
                "skills": [
                    {
                        "name": "Component Testing with Vitest",
                        "desc": "Testing user interactions rather than implementation details.",
                        "tools": ["Vitest", "React Testing Library"],
                        "interview_tip": "Explain why queries like getByRole are preferred over getByTestId for accessibility."
                    },
                    {
                        "name": "End-to-End (E2E) with Playwright",
                        "desc": "Automating critical user journeys like authentication, cart checkout, and form submissions.",
                        "tools": ["Playwright", "GitHub Actions"],
                        "interview_tip": "Describe how to test resilience against network latency and mock API error responses in Playwright."
                    }
                ]
            }
        ],
        "faqs": [
            {
                "q": "Is React still the dominant frontend library in 2026?",
                "a": "Yes. React and Next.js continue to power the vast majority of modern enterprise web apps and have the highest volume of open job requisitions globally."
            },
            {
                "q": "Do frontend engineers need to know backend concepts?",
                "a": "With Next.js App Router, Server Actions, and BFF (Backend-for-Frontend) architectures, frontend engineers are expected to understand API design, HTTP cookies, and server rendering."
            }
        ],
        "mindmap_root": {
            "name": "Frontend & React",
            "children": [
                {
                    "name": "TypeScript & Core",
                    "children": [{"name": "Strict Types"}, {"name": "Async & Promises"}, {"name": "DOM & Events"}]
                },
                {
                    "name": "React 19 & Next.js",
                    "children": [{"name": "Server Components"}, {"name": "Hooks & Context"}, {"name": "Next.js App Router"}]
                },
                {
                    "name": "Styling & UI",
                    "children": [{"name": "Tailwind CSS"}, {"name": "Radix / shadcn"}, {"name": "Responsive Design"}]
                },
                {
                    "name": "Performance",
                    "children": [{"name": "Core Web Vitals"}, {"name": "Code Splitting"}, {"name": "Profiler"}]
                },
                {
                    "name": "Testing",
                    "children": [{"name": "Vitest"}, {"name": "React Testing Library"}, {"name": "Playwright E2E"}]
                }
            ]
        }
    },

    "data-scientist": {
        "slug": "data-scientist",
        "role_name": "Data Scientist",
        "h1_title": "Data Scientist Roadmap 2026",
        "seo_title": "Data Scientist Roadmap 2026: Math, Python, ML & Production | ResuMate",
        "meta_desc": "Definitive 2026 Data Science career roadmap. Learn statistics, SQL, pandas, machine learning, deep learning, LLMs, and real-world deployment.",
        "tagline": "Turn messy enterprise data into high-accuracy predictive models, statistical insights, and business value.",
        "avg_salary": "$120,000 – $175,000 / yr",
        "est_time": "5 – 7 Months",
        "demand_level": "High 📊",
        "overview": (
            "Data Science in 2026 bridges classical statistics, predictive machine learning, and modern Generative AI. "
            "Companies expect candidates to conduct rigorous A/B experimentation, extract complex features with SQL and Python, "
            "train gradient boosted trees and neural networks, and deploy models into production services."
        ),
        "phases": [
            {
                "num": 1,
                "title": "Mathematics & Practical Statistics",
                "badge": "Phase 1 · Theory & Math",
                "summary": "Building the statistical and mathematical foundation for model confidence.",
                "skills": [
                    {
                        "name": "Hypothesis Testing & A/B Testing",
                        "desc": "P-values, statistical power, confidence intervals, sample size determination, and multi-armed bandits.",
                        "tools": ["Scipy", "Statsmodels"],
                        "interview_tip": "Be ready to calculate minimum sample size and explain how to avoid peeking bias in A/B experiments."
                    },
                    {
                        "name": "Linear Algebra & Probability",
                        "desc": "Eigenvalues, matrix factorization, Bayes' theorem, probability distributions, and likelihood functions.",
                        "tools": ["NumPy", "Linear Algebra"],
                        "interview_tip": "Interviews often ask you to derive linear regression or explain PCA through eigenvalue decomposition."
                    }
                ]
            },
            {
                "num": 2,
                "title": "Data Wrangling & Exploration",
                "badge": "Phase 2 · Feature Prep",
                "summary": "Extracting, cleaning, and transforming terabytes of structured and semi-structured data.",
                "skills": [
                    {
                        "name": "Advanced SQL & Warehousing",
                        "desc": "Window functions (ROW_NUMBER, LAG, LEAD), cumulative metrics, cohort analysis, and Snowflake/BigQuery queries.",
                        "tools": ["PostgreSQL", "Snowflake", "BigQuery"],
                        "interview_tip": "Expect live SQL challenges calculating retention rates or moving averages across rolling windows."
                    },
                    {
                        "name": "Pandas & Polars Data Manipulation",
                        "desc": "High-performance tabular manipulation, vectorization, handling missing data, and encoding strategies.",
                        "tools": ["Pandas", "Polars", "PyArrow"],
                        "interview_tip": "Explain why vectorization in NumPy/Polars is orders of magnitude faster than iterating with Python for loops."
                    }
                ]
            },
            {
                "num": 3,
                "title": "Supervised & Unsupervised Machine Learning",
                "badge": "Phase 3 · Machine Learning",
                "summary": "Developing robust models that generalize without overfitting.",
                "skills": [
                    {
                        "name": "Gradient Boosted Decision Trees",
                        "desc": "Tabular data champions: hyperparameter tuning, handling class imbalance, and cross-validation.",
                        "tools": ["XGBoost", "LightGBM", "CatBoost", "Scikit-Learn"],
                        "interview_tip": "Explain the difference between Bagging (Random Forest) and Boosting (XGBoost) and how each affects bias and variance."
                    },
                    {
                        "name": "Model Evaluation & Interpretability",
                        "desc": "ROC-AUC, Precision-Recall curves, SHAP values, feature importance, and confusion matrix diagnostics.",
                        "tools": ["SHAP", "Scikit-Learn Metrics"],
                        "interview_tip": "Explain why Accuracy is misleading for imbalanced datasets (e.g. fraud detection) and why PR-AUC is preferred."
                    }
                ]
            },
            {
                "num": 4,
                "title": "Deep Learning & Applied Generative AI",
                "badge": "Phase 4 · Modern AI",
                "summary": "Harnessing neural networks, embeddings, and foundational LLM integrations.",
                "skills": [
                    {
                        "name": "PyTorch Fundamentals",
                        "desc": "Tensors, autograd, forward/backward passes, loss functions, and building multi-layer perceptrons.",
                        "tools": ["PyTorch", "TorchVision"],
                        "interview_tip": "Walk through how backpropagation computes gradients using the chain rule."
                    },
                    {
                        "name": "Embeddings & Vector Search",
                        "desc": "Semantic search, text embeddings, cosine similarity, and Retrieval-Augmented Generation (RAG).",
                        "tools": ["SentenceTransformers", "pgvector", "LangChain"],
                        "interview_tip": "Explain how RAG grounds language models with private company data to eliminate hallucinations."
                    }
                ]
            }
        ],
        "faqs": [
            {
                "q": "Do Data Scientists need to write production software?",
                "a": "Yes. Modern employers expect Data Scientists to write modular, tested Python code, package models into Docker containers, and deliver clean APIs."
            },
            {
                "q": "What is the difference between a Data Scientist and a Machine Learning Engineer?",
                "a": "Data Scientists focus heavily on business experimentation, hypothesis testing, insights, and model prototyping. Machine Learning Engineers focus on scaling models, low-latency inference pipelines, and MLOps infrastructure."
            }
        ],
        "mindmap_root": {
            "name": "Data Scientist",
            "children": [
                {
                    "name": "Math & Stats",
                    "children": [{"name": "A/B Testing"}, {"name": "Probability & Distributions"}, {"name": "Linear Algebra"}]
                },
                {
                    "name": "Data Wrangling",
                    "children": [{"name": "Advanced SQL"}, {"name": "Pandas & Polars"}, {"name": "Feature Engineering"}]
                },
                {
                    "name": "Machine Learning",
                    "children": [{"name": "XGBoost & LightGBM"}, {"name": "Cross Validation"}, {"name": "SHAP Explainability"}]
                },
                {
                    "name": "Deep Learning & LLM",
                    "children": [{"name": "PyTorch"}, {"name": "Embeddings & Vectors"}, {"name": "RAG Pipelines"}]
                },
                {
                    "name": "Delivery",
                    "children": [{"name": "Docker & APIs"}, {"name": "Streamlit Dashboards"}]
                }
            ]
        }
    },

    "devops-engineer": {
        "slug": "devops-engineer",
        "role_name": "DevOps & Cloud Engineer",
        "h1_title": "DevOps & Cloud Engineer Roadmap 2026",
        "seo_title": "DevOps & Cloud Engineer Roadmap 2026: Kubernetes, CI/CD, Terraform | ResuMate",
        "meta_desc": "Comprehensive 2026 DevOps engineering roadmap. Learn Linux, Docker, Kubernetes, Terraform IaC, GitHub Actions CI/CD, and AWS cloud architecture.",
        "tagline": "Automate infrastructure, build zero-downtime deployment pipelines, and ensure 99.99% system reliability.",
        "avg_salary": "$125,000 – $180,000 / yr",
        "est_time": "5 – 6 Months",
        "demand_level": "Extremely High 🔥",
        "overview": (
            "DevOps and Platform Engineering in 2026 focus on GitOps automation, container orchestration with Kubernetes, "
            "declarative Infrastructure as Code (Terraform), and robust observability. Top companies test your ability to debug "
            "distributed systems, automate secure deployment pipelines, and optimize cloud infrastructure costs."
        ),
        "phases": [
            {
                "num": 1,
                "title": "Linux Systems & Networking Fundamentals",
                "badge": "Phase 1 · Foundation",
                "summary": "Mastering the operating system environment where all cloud workloads live.",
                "skills": [
                    {
                        "name": "Linux Administration & Bash",
                        "desc": "Systemd services, process management (htop, lsof), disk I/O, permissions, and shell automation.",
                        "tools": ["Bash", "systemd", "SSH", "Linux CLI"],
                        "interview_tip": "Be ready to troubleshoot high CPU load and identify zombie or leaking processes in Linux."
                    },
                    {
                        "name": "TCP/IP, DNS & Networking",
                        "desc": "HTTP/HTTPS protocols, TLS certificates, DNS records (A, CNAME, TXT), subnets, and firewalls.",
                        "tools": ["curl", "dig", "iptables", "Wireshark"],
                        "interview_tip": "Classic interview question: Explain step-by-step what happens when a user types a URL into a browser."
                    }
                ]
            },
            {
                "num": 2,
                "title": "Containers & Kubernetes Orchestration",
                "badge": "Phase 2 · Containers",
                "summary": "Packaging and orchestrating applications reliably across cloud clusters.",
                "skills": [
                    {
                        "name": "Docker & Container Security",
                        "desc": "Multi-stage builds, non-root users, vulnerability scanning, and Docker Compose environments.",
                        "tools": ["Docker", "Trivy", "Containerd"],
                        "interview_tip": "Explain why running Docker containers as root poses severe host security risks."
                    },
                    {
                        "name": "Kubernetes (K8s) Core",
                        "desc": "Pods, Deployments, Services, ConfigMaps, Secrets, Ingress, and Horizontal Pod Autoscaling (HPA).",
                        "tools": ["Kubernetes", "kubectl", "Helm"],
                        "interview_tip": "Explain how Kubernetes rolling updates maintain zero downtime during a deployment."
                    }
                ]
            },
            {
                "num": 3,
                "title": "Infrastructure as Code (IaC) & Cloud",
                "badge": "Phase 3 · Cloud Automation",
                "summary": "Managing cloud infrastructure reproducibly with declarative code.",
                "skills": [
                    {
                        "name": "Terraform & OpenTofu",
                        "desc": "State management, remote backends with S3/DynamoDB locks, modules, and plan/apply workflows.",
                        "tools": ["Terraform", "OpenTofu"],
                        "interview_tip": "Discuss how Terraform state locking prevents conflicting concurrent infrastructure changes."
                    },
                    {
                        "name": "AWS Cloud Architecture",
                        "desc": "VPC networking, IAM least-privilege security, ECS/EKS compute, S3, and RDS Aurora.",
                        "tools": ["AWS IAM", "AWS VPC", "AWS EKS", "AWS S3"],
                        "interview_tip": "Design a multi-AZ highly available web architecture resilient to single datacenter failures."
                    }
                ]
            },
            {
                "num": 4,
                "title": "CI/CD Automation & Observability",
                "badge": "Phase 4 · SRE & Pipelines",
                "summary": "Delivering software with confidence and monitoring production health in real time.",
                "skills": [
                    {
                        "name": "CI/CD Pipelines & GitOps",
                        "desc": "GitHub Actions workflows, automated testing gates, semantic versioning, and ArgoCD deployment.",
                        "tools": ["GitHub Actions", "ArgoCD"],
                        "interview_tip": "Describe GitOps: why storing infrastructure and deployment state in Git provides superior auditability."
                    },
                    {
                        "name": "Observability & APM",
                        "desc": "Metrics collection, OpenTelemetry distributed tracing, log aggregation, and SLO/SLA alerting.",
                        "tools": ["Prometheus", "Grafana", "OpenTelemetry", "Datadog"],
                        "interview_tip": "Explain the four golden signals of monitoring: Latency, Traffic, Errors, and Saturation."
                    }
                ]
            }
        ],
        "faqs": [
            {
                "q": "Should I learn AWS or GCP first for DevOps?",
                "a": "AWS has the highest global market share and job volume, making it the most versatile first cloud provider to learn. The principles (VPC, IAM, compute, storage) transfer easily to GCP or Azure."
            },
            {
                "q": "Is Kubernetes required for junior or entry-level DevOps roles?",
                "a": "Understanding Docker containers and Linux fundamentals is essential first. However, having hands-on familiarity with Kubernetes resources (Deployments, Services) immediately differentiates you from other applicants."
            }
        ],
        "mindmap_root": {
            "name": "DevOps Engineer",
            "children": [
                {
                    "name": "Linux & Networking",
                    "children": [{"name": "Bash & Shell"}, {"name": "Systemd"}, {"name": "DNS & TCP/IP"}]
                },
                {
                    "name": "Containers & K8s",
                    "children": [{"name": "Docker Multi-stage"}, {"name": "Kubernetes Pods & Services"}, {"name": "Helm Charts"}]
                },
                {
                    "name": "IaC & AWS",
                    "children": [{"name": "Terraform State"}, {"name": "AWS VPC & IAM"}, {"name": "ECS / EKS"}]
                },
                {
                    "name": "CI/CD & SRE",
                    "children": [{"name": "GitHub Actions"}, {"name": "Prometheus & Grafana"}, {"name": "OpenTelemetry"}]
                }
            ]
        }
    }
}


def get_all_tracks():
    return list(TRACKS_DATA.values())


def get_track_by_slug(slug: str):
    return TRACKS_DATA.get(slug.lower().strip())

