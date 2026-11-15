import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

# Pre-curated, industry-standard skill taxonomies for fast and offline-reliable mindmaps
CURATED_ROADMAPS = {
    "python": {
        "name": "Python Developer",
        "children": [
            {
                "name": "Core Language & Idioms",
                "children": [
                    {"name": "Data Structures & Collections"},
                    {"name": "OOP & Metaclasses"},
                    {"name": "Decorators, Generators & Iterators"},
                    {"name": "Type Hinting & Pydantic"},
                    {"name": "Asyncio & Concurrency"}
                ]
            },
            {
                "name": "Web Frameworks",
                "children": [
                    {"name": "FastAPI & Pydantic v2"},
                    {"name": "Django & Django REST Framework"},
                    {"name": "Flask & Jinja2"},
                    {"name": "WebSocket & Realtime APIs"},
                    {"name": "Authentication (JWT, OAuth2)"}
                ]
            },
            {
                "name": "Databases & Storage",
                "children": [
                    {"name": "PostgreSQL & Advanced SQL"},
                    {"name": "SQLAlchemy 2.0 & Alembic"},
                    {"name": "Redis (Caching & Queues)"},
                    {"name": "MongoDB & NoSQL"},
                    {"name": "Connection Pooling & Optimization"}
                ]
            },
            {
                "name": "Testing & Code Quality",
                "children": [
                    {"name": "Pytest, Fixtures & Parametrize"},
                    {"name": "Mocking & FactoryBoy"},
                    {"name": "Ruff, Flake8 & Black"},
                    {"name": "MyPy Static Typing"},
                    {"name": "Integration & Load Testing"}
                ]
            },
            {
                "name": "APIs & Distributed Systems",
                "children": [
                    {"name": "Celery & Background Workers"},
                    {"name": "RabbitMQ / Apache Kafka"},
                    {"name": "gRPC & Protocol Buffers"},
                    {"name": "Rate Limiting & API Gateways"}
                ]
            },
            {
                "name": "DevOps & Cloud",
                "children": [
                    {"name": "Docker & Multi-Stage Builds"},
                    {"name": "GitHub Actions & CI/CD"},
                    {"name": "AWS (ECS, Lambda, S3)"},
                    {"name": "Gunicorn / Uvicorn Tuning"}
                ]
            }
        ]
    },
    "frontend": {
        "name": "Frontend Developer",
        "children": [
            {
                "name": "Modern JavaScript & TypeScript",
                "children": [
                    {"name": "ES6+ Syntax & Features"},
                    {"name": "TypeScript Strict Mode"},
                    {"name": "DOM Manipulation & Events"},
                    {"name": "Async/Await & Promises"},
                    {"name": "Web Workers & Streams"}
                ]
            },
            {
                "name": "CSS Architecture & UI",
                "children": [
                    {"name": "CSS Grid & Flexbox"},
                    {"name": "Tailwind CSS & Utility-First"},
                    {"name": "CSS Modules & PostCSS"},
                    {"name": "Responsive Design & Mobile-First"},
                    {"name": "Animations & Micro-interactions"}
                ]
            },
            {
                "name": "React & Modern Frameworks",
                "children": [
                    {"name": "React 19 & Server Components"},
                    {"name": "Next.js App Router & SSR"},
                    {"name": "Hooks & Custom Hook Architecture"},
                    {"name": "State Management (Zustand, Redux Toolkit)"},
                    {"name": "TanStack Query & Data Fetching"}
                ]
            },
            {
                "name": "Performance & Web Vitals",
                "children": [
                    {"name": "Core Web Vitals (LCP, INP, CLS)"},
                    {"name": "Code Splitting & Dynamic Imports"},
                    {"name": "Bundle Optimization & Tree Shaking"},
                    {"name": "Image Optimization & CDN Caching"}
                ]
            },
            {
                "name": "Testing & Build Tools",
                "children": [
                    {"name": "Vite & Modern Bundlers"},
                    {"name": "Vitest & React Testing Library"},
                    {"name": "Playwright E2E Automation"},
                    {"name": "ESLint & Prettier Tooling"}
                ]
            }
        ]
    },
    "full stack": {
        "name": "Full Stack Developer",
        "children": [
            {
                "name": "Frontend Mastery",
                "children": [
                    {"name": "TypeScript & React"},
                    {"name": "Next.js Fullstack Architecture"},
                    {"name": "Responsive UI & Tailwind CSS"},
                    {"name": "State Management & Optimistic UI"}
                ]
            },
            {
                "name": "Backend & API Design",
                "children": [
                    {"name": "Node.js / Python / Go"},
                    {"name": "REST & GraphQL API Design"},
                    {"name": "JWT, Session & OAuth2 Auth"},
                    {"name": "WebSockets & Event Streams"}
                ]
            },
            {
                "name": "Data & Persistence",
                "children": [
                    {"name": "PostgreSQL & Schema Migration"},
                    {"name": "Prisma / SQLAlchemy ORMs"},
                    {"name": "Redis In-Memory Caching"},
                    {"name": "Vector Databases (pgvector, Pinecone)"}
                ]
            },
            {
                "name": "DevOps & Cloud Deployment",
                "children": [
                    {"name": "Docker & Containerization"},
                    {"name": "Vercel & AWS Cloud Deployments"},
                    {"name": "GitHub Actions CI/CD"},
                    {"name": "Monitoring, Logging & APM"}
                ]
            },
            {
                "name": "System Design & Architecture",
                "children": [
                    {"name": "Microservices vs Modular Monolith"},
                    {"name": "Message Queues & Background Jobs"},
                    {"name": "Rate Limiting & Security (OWASP)"},
                    {"name": "Horizontal Scalability & CDN"}
                ]
            }
        ]
    },
    "data science": {
        "name": "Data Scientist",
        "children": [
            {
                "name": "Mathematics & Statistics",
                "children": [
                    {"name": "Probability & Distributions"},
                    {"name": "Hypothesis Testing & A/B Tests"},
                    {"name": "Linear Algebra & Matrices"},
                    {"name": "Multivariable Calculus & Gradients"}
                ]
            },
            {
                "name": "Programming & Data Wrangling",
                "children": [
                    {"name": "Python & NumPy / Pandas"},
                    {"name": "SQL & Complex Window Functions"},
                    {"name": "Data Cleaning & Imputation"},
                    {"name": "Polars & High-Performance Dataframes"}
                ]
            },
            {
                "name": "Machine Learning",
                "children": [
                    {"name": "Supervised Learning (Scikit-Learn)"},
                    {"name": "Gradient Boosting (XGBoost, LightGBM)"},
                    {"name": "Feature Engineering & Selection"},
                    {"name": "Model Evaluation (ROC-AUC, F1-Score)"}
                ]
            },
            {
                "name": "Deep Learning & AI",
                "children": [
                    {"name": "PyTorch Fundamentals"},
                    {"name": "Neural Network Architectures"},
                    {"name": "NLP & Hugging Face Transformers"},
                    {"name": "LLM Fine-Tuning & Prompting"}
                ]
            },
            {
                "name": "Visualization & Communication",
                "children": [
                    {"name": "Matplotlib, Seaborn & Plotly"},
                    {"name": "Tableau / Streamlit Dashboards"},
                    {"name": "Executive Storytelling & Insights"}
                ]
            }
        ]
    },
    "devops": {
        "name": "DevOps Engineer",
        "children": [
            {
                "name": "Linux & OS Engineering",
                "children": [
                    {"name": "Shell Scripting (Bash / Zsh)"},
                    {"name": "Systemd & Process Management"},
                    {"name": "Linux Networking & Firewalls"},
                    {"name": "Storage, Filesystems & Permissions"}
                ]
            },
            {
                "name": "Containers & Orchestration",
                "children": [
                    {"name": "Docker & Container Security"},
                    {"name": "Kubernetes (K8s) Architecture"},
                    {"name": "Helm Charts & Package Management"},
                    {"name": "Ingress Controllers & Service Meshes"}
                ]
            },
            {
                "name": "Infrastructure as Code",
                "children": [
                    {"name": "Terraform & OpenTofu"},
                    {"name": "Ansible & Configuration Automation"},
                    {"name": "CloudFormation & AWS CDK"},
                    {"name": "State Management & Module Design"}
                ]
            },
            {
                "name": "CI/CD & GitOps",
                "children": [
                    {"name": "GitHub Actions Pipelines"},
                    {"name": "ArgoCD & GitOps Workflows"},
                    {"name": "Automated Testing & Security Gates"},
                    {"name": "Semantic Versioning & Release Automation"}
                ]
            },
            {
                "name": "Observability & SRE",
                "children": [
                    {"name": "Prometheus & Grafana Dashboards"},
                    {"name": "OpenTelemetry & Tracing"},
                    {"name": "Log Aggregation (ELK, Datadog)"},
                    {"name": "Incident Response & SLO/SLA Design"}
                ]
            }
        ]
    }
}

def get_curated_fallback(role_clean: str) -> dict:
    rc = role_clean.lower()
    for key, data in CURATED_ROADMAPS.items():
        if key in rc:
            result = json.loads(json.dumps(data))
            result["name"] = role_clean
            return result
    
    # Generic intelligent fallback
    return {
        "name": role_clean,
        "children": [
            {
                "name": "Foundational Competencies",
                "children": [
                    {"name": "Core Principles & Mental Models"},
                    {"name": "Fundamental Tools & Environments"},
                    {"name": "Standard Industry Workflows"}
                ]
            },
            {
                "name": "Key Technologies & Frameworks",
                "children": [
                    {"name": "Primary Language / Platform"},
                    {"name": "Industry-Standard Frameworks"},
                    {"name": "Data Management & Storage"}
                ]
            },
            {
                "name": "Advanced Architecture",
                "children": [
                    {"name": "Scalability & Performance"},
                    {"name": "Security & Best Practices"},
                    {"name": "System Design & Integration"}
                ]
            },
            {
                "name": "Testing & Reliability",
                "children": [
                    {"name": "Automated Quality Assurance"},
                    {"name": "Debugging & Profiling"},
                    {"name": "Benchmarking & Verification"}
                ]
            },
            {
                "name": "Production Delivery & Collaboration",
                "children": [
                    {"name": "Version Control & Collaboration"},
                    {"name": "CI/CD & Automated Releases"},
                    {"name": "Monitoring & Incident Handling"}
                ]
            }
        ]
    }


def generate_mindmap(role: str) -> dict:
    clean_role = (role or "Software Engineer").strip()
    # Deduplicate repetitive strings e.g. "DeveloperDeveloper"
    clean_role = re.sub(r'(Developer|Engineer|Architect|Designer|Manager)\1+', r'\1', clean_role, flags=re.IGNORECASE)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return get_curated_fallback(clean_role)

    prompt = f"""
    You are an expert career advisor and industry hiring manager.
    Your task is to design a structured career roadmap for the role: {clean_role}.

    RULES:
    1. Root node name must be "{clean_role}".
    2. Provide 5-6 high-level competency categories under "children".
    3. Each category must have 3-5 concrete, technical, modern skills/tools.
    4. Avoid generic items like "Documentation" or "Learning Ability".
    5. Return ONLY a valid JSON object matching this structure:
    {{
      "name": "{clean_role}",
      "children": [
        {{
          "name": "Category Name",
          "children": [{{"name": "Skill 1"}}, {{"name": "Skill 2"}}]
        }}
      ]
    }}
    """

    models_to_try = ["openai/gpt-4o-mini", "meta-llama/llama-3.1-8b-instruct"]
    
    try:
        from openai import OpenAI
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            timeout=8.0,
            max_retries=1,
        )

        for model in models_to_try:
            try:
                response = client.chat.completions.create(
                    model=model,
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1200,
                )
                raw = (response.choices[0].message.content or "").strip()
                cleaned = raw.replace("```json", "").replace("```", "").strip()
                if "{" in cleaned and "}" in cleaned:
                    cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}")+1]
                data = json.loads(cleaned)
                if isinstance(data, dict) and "children" in data and len(data["children"]) >= 3:
                    if "name" not in data or not data["name"]:
                        data["name"] = clean_role
                    return data
            except Exception as model_err:
                print(f"[mindmap] Model {model} attempt failed: {model_err}")
                continue
    except Exception as e:
        print(f"[mindmap] Client initialization or request failed: {e}")

    # Seamless fallback to curated high-quality roadmap
    return get_curated_fallback(clean_role)


def get_skill_info(skill: str) -> dict:
    clean_skill = (skill or "Software Engineering").strip()
    
    # Check if we can query LLM with timeout
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
                timeout=6.0,
                max_retries=1,
            )
            prompt = f"Provide a brief 2-sentence description of the skill '{clean_skill}' and 3 learning resource links (Label and URL) in JSON format: {{\"description\": \"...\", \"resources\": [{{\"label\": \"...\", \"url\": \"https://...\"}}]}}"
            response = client.chat.completions.create(
                model="openai/gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.2,
            )
            raw = (response.choices[0].message.content or "").strip()
            cleaned = raw.replace("```json", "").replace("```", "").strip()
            if "{" in cleaned and "}" in cleaned:
                cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}")+1]
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "description" in parsed:
                return parsed
        except Exception as e:
            print(f"[skill-info] LLM fetch failed for {clean_skill}: {e}")

    # Fallback default knowledge & resources
    encoded = clean_skill.replace(" ", "+")
    return {
        "description": f"Mastery of {clean_skill} is essential for industry-standard development, system design, and production engineering workflows.",
        "resources": [
            {"label": f"{clean_skill} Official Docs & Guides", "url": f"https://www.google.com/search?q={encoded}+official+documentation"},
            {"label": f"{clean_skill} Deep-Dive on Roadmap.sh", "url": f"https://roadmap.sh"},
            {"label": f"{clean_skill} FreeCodeCamp & Tutorials", "url": f"https://www.freecodecamp.org/news/search/?query={encoded}"}
        ]
    }

