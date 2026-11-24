import json
import logging
import re
import time
from fastapi import Request
import db.backend as db
from core.config import logger, FREE_RESUME_DAILY_LIMIT
from core.security import current_user_plan
from services.coding.coding_platform import submission_ts_column

DEFAULT_ATHUL_RESUME = r"""\documentclass[a4paper,9.5pt]{article}

% -------------------------
% Layout
% -------------------------
\usepackage[top=0.30in, bottom=0.30in, left=0.45in, right=0.45in]{geometry}

% -------------------------
% Packages
% -------------------------
\usepackage{enumitem, titlesec, hyperref, fontawesome5}
\usepackage{helvet}
\renewcommand{\familydefault}{\sfdefault}

\hypersetup{colorlinks=true, linkcolor=black, urlcolor=black}

% -------------------------
% Spacing
% -------------------------
\renewcommand{\baselinestretch}{1.08}
\setlength{\parskip}{0pt}
\setlength{\parsep}{0pt}

\titlespacing*{\section}{0pt}{7pt}{1pt}


\titleformat{\section}{\normalsize\bfseries\uppercase}{}{0em}{}[\titlerule]

% Custom compact list
\newcommand{\resumeItemListStart}{\begin{itemize}[leftmargin=1.2em, itemsep=0pt, topsep=1pt, parsep=0pt, partopsep=0pt]}
\newcommand{\resumeItemListEnd}{\end{itemize}}
\newcommand{\resumeItem}[1]{\item\small{#1}}

% Sub-list
\newcommand{\resumeSubListStart}{\begin{itemize}[leftmargin=1.5em, itemsep=0pt, topsep=0pt, parsep=0pt, partopsep=0pt, label={--}]}
\newcommand{\resumeSubListEnd}{\end{itemize}}

\begin{document}

% -------------------------
% Header
% -------------------------
\begin{center}
    {\huge \textbf{ATHUL ARIGA}} \\[2pt]
    \small
    \href{mailto:athulariga12@gmail.com}{\faEnvelope\ athulariga12@gmail.com} \ $|$ \
    \href{https://linkedin.com/in/athul-ariga}{\faLinkedin\ in/athul-ariga} \ $|$ \
    \href{https://github.com/ATHULARIGA}{\faGithub\ github.com/ATHULARIGA} \ $|$ \
    \faPhone\ +91 9481977128 \ $|$ \
    \faMapMarker*\ Bengaluru, India
\end{center}

\vspace{-4pt}

% -------------------------
% Technical Skills
% -------------------------
\section*{Technical Skills}
\vspace{1pt}
\small{
\textbf{Languages:} Python (Proficient), SQL (Advanced), JavaScript, HTML5/CSS3 \\
\textbf{Data Engineering \& Big Data:} Apache Spark (PySpark), Apache Airflow, Kafka, Delta Lake, Snowflake, DBT \\
\textbf{Cloud \& Platforms:} Microsoft Fabric, Azure (ADLS Gen2, Data Factory, Databricks), AWS (S3, Redshift) \\
\textbf{Databases \& Tools:} PostgreSQL, MySQL, DuckDB, MongoDB, Git, Docker, CI/CD pipelines, Jupyter, dbt \\
\textbf{Frameworks \& Libraries:} FastAPI, Pandas, NumPy, Scikit-learn, Great Expectations, SQLAlchemy, Polars \\
\textbf{Core Concepts:} ETL/ELT Pipeline Design, Data Modeling (Star/Snowflake), Data Warehousing, Data Governance
}

\vspace{0.5pt}

% -------------------------
% Professional Experience
% -------------------------
\section*{Professional Experience}
\vspace{1pt}

\noindent\textbf{Associate Consultant – Data Engineer} \hfill \textbf{Oct 2023 – Present} \\
\textit{Capgemini Technology Services} \hfill \textit{Bengaluru, India}
\resumeItemListStart
    \resumeItem{Designed, deployed, and maintained \textbf{20+ production-grade ETL/ELT data pipelines} on Microsoft Fabric and Azure Synapse, processing \textbf{1.5TB+ daily enterprise data} with 99.8\% job success rate and SLA compliance.}
    \resumeItem{Engineered PySpark and Delta Lake data transformation workflows across Bronze, Silver, and Gold lakehouse architectures, cutting pipeline execution runtimes by \textbf{38\%} through optimal partition and caching strategies.}
    \resumeItem{Built and orchestrated complex, dependency-aware batch workflows with \textbf{Apache Airflow} and Azure Data Factory (ADF), reducing manual monitoring intervention by \textbf{70\%} with automated Slack/email alerting.}
    \resumeItem{Standardized rigorous data quality control frameworks using Great Expectations and custom SQL validation gates, identifying and quarantining 99.4\% of anomalous source data before ingestion into reporting data marts.}
    \resumeItem{Authored parameterized SQL stored procedures, views, and complex aggregations on Synapse Analytics / Snowflake serving executive Power BI reporting dashboards with sub-second query latency.}
\resumeItemListEnd

\vspace{2pt}

\noindent\textbf{Data Engineering \& Python Intern} \hfill \textbf{Feb 2023 – Aug 2023} \\
\textit{Tech Solutions Lab} \hfill \textit{Mangaluru, India}
\resumeItemListStart
    \resumeItem{Developed automated web-scraping and data extraction workers in Python utilizing BeautifulSoup, Scrapy, and Pandas to collect, clean, and normalize structured data from 15+ external job and pricing portals.}
    \resumeItem{Implemented PostgreSQL relational database schemas, indexes, and automated data migration scripts that improved analytical aggregation query performance by \textbf{45\%}.}
    \resumeItem{Created REST API endpoints using \textbf{FastAPI} with Pydantic validation schemas to serve sanitized datasets to frontend internal analytics platforms.}
\resumeItemListEnd

\vspace{0.5pt}

% -------------------------
% Key Projects
% -------------------------
\section*{Key Projects}
\vspace{1pt}

\noindent\textbf{AI-Powered Career Intelligence Platform (CareerAI)} \hfill \href{https://github.com/ATHULARIGA}{\small\faExternalLink*\ Project Link} \\
\textit{Python, FastAPI, OpenAI API, PostgreSQL, SQLite, Docker, Jinja2}
\resumeItemListStart
    \resumeItem{Architected and shipped an end-to-end full-stack SaaS platform providing instant ATS resume scoring, dimensional skill gap analysis, interactive coding sandboxes, and AI-driven mock interview simulations.}
    \resumeItem{Engineered semantic NLP comparison pipelines matching candidate CV content against live job descriptions using vector embeddings and BM25 hybrid ranking models, achieving \textbf{94\% parsing accuracy}.}
    \resumeItem{Engineered a high-throughput, sandboxed multi-language code evaluation runner executing Python, JavaScript, Java, and C++ code against private test suites with memory and execution-time bounds.}
\resumeItemListEnd

\vspace{2pt}

\noindent\textbf{Enterprise Lakehouse Real-time Streaming Pipeline} \hfill \href{https://github.com/ATHULARIGA}{\small\faExternalLink*\ Project Link} \\
\textit{Apache Kafka, PySpark Structured Streaming, Delta Lake, Docker, MinIO}
\resumeItemListStart
    \resumeItem{Implemented real-time data streaming pipeline ingesting clickstream and IoT telemetry event streams from Apache Kafka topics into Delta Lake ACID storage tables at 10,000+ events/sec.}
    \resumeItem{Engineered stateful watermark aggregations and deduplication logic in PySpark, achieving end-to-end event-to-dashboard ingestion latency of \textbf{under 4 seconds}.}
\resumeItemListEnd

\vspace{0.5pt}

% -------------------------
% Education
% -------------------------
\section*{Education}
\vspace{1pt}

\noindent\textbf{B.E. in Computer Science \& Engineering} – Sahyadri College of Engineering and Management, VTU \hfill \textbf{2019 – 2023}

\vspace{0.5pt}

% -------------------------
% Achievements
% -------------------------
\section*{Certifications \& Achievements}
\vspace{1pt}
\resumeSubListStart
    \resumeItem{Pitched \textbf{Elavo} at MSME Karnataka Government Pitch Fest — selected among state-level startups}
    \resumeItem{\textbf{2nd place} – Bot Race competition, Sahyadri College Tech Fest}
    
\resumeSubListEnd


\end{document}
"""


def _ensure_auth_tables() -> None:
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, 
        """
        CREATE TABLE IF NOT EXISTS auth_rate_limits(
            rate_key TEXT PRIMARY KEY,
            window_start INTEGER NOT NULL,
            attempts INTEGER NOT NULL,
            blocked_until INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def init_resume_tables() -> None:
    conn = db.get_conn()
    cur = conn.cursor()
    id_col = db.id_pk_col()
    db.execute(cur, 
        f"""
        CREATE TABLE IF NOT EXISTS resume_reports(
            id {id_col},
            user_email TEXT NOT NULL,
            target_role TEXT,
            overall REAL,
            ats REAL,
            keyword_coverage REAL,
            status TEXT,
            report_json TEXT NOT NULL,
            created_ts INTEGER NOT NULL
        )
        """
    )
    db.execute(cur, "CREATE INDEX IF NOT EXISTS idx_resume_reports_user_ts ON resume_reports(user_email, created_ts DESC)")
    if db.is_postgres():
        cur.execute("SELECT pg_get_serial_sequence('resume_reports', 'id')")
        seq_row = cur.fetchone()
        if seq_row and seq_row[0]:
            seq_name = seq_row[0]
            cur.execute('SELECT COALESCE(MAX(id), 0) + 1 FROM "resume_reports"')
            next_id = int(cur.fetchone()[0])
            cur.execute("SELECT setval(%s, %s, false)", (seq_name, next_id))
    conn.commit()
    conn.close()


def init_user_tables() -> None:
    conn = db.get_conn()
    cur = conn.cursor()
    id_col = db.id_pk_col()
    db.execute(cur, 
        f"""
        CREATE TABLE IF NOT EXISTS users(
            id {id_col},
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            plan TEXT NOT NULL DEFAULT 'free',
            premium_since INTEGER NOT NULL DEFAULT 0,
            premium_expires_ts INTEGER NOT NULL DEFAULT 0,
            reset_token TEXT,
            reset_token_expiry INTEGER NOT NULL DEFAULT 0,
            password_updated_ts INTEGER NOT NULL DEFAULT 0,
            created_ts INTEGER NOT NULL
        )
        """
    )
    cols = db.list_columns(conn, "users")
    if "role" not in cols:
        db.execute(cur, "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    if "reset_token" not in cols:
        db.execute(cur, "ALTER TABLE users ADD COLUMN reset_token TEXT")
    if "reset_token_expiry" not in cols:
        db.execute(cur, "ALTER TABLE users ADD COLUMN reset_token_expiry INTEGER NOT NULL DEFAULT 0")
    if "password_updated_ts" not in cols:
        db.execute(cur, "ALTER TABLE users ADD COLUMN password_updated_ts INTEGER NOT NULL DEFAULT 0")
    if "plan" not in cols:
        db.execute(cur, "ALTER TABLE users ADD COLUMN plan TEXT NOT NULL DEFAULT 'free'")
    if "premium_since" not in cols:
        db.execute(cur, "ALTER TABLE users ADD COLUMN premium_since INTEGER NOT NULL DEFAULT 0")
    if "premium_expires_ts" not in cols:
        db.execute(cur, "ALTER TABLE users ADD COLUMN premium_expires_ts INTEGER NOT NULL DEFAULT 0")
    if "auth_provider" not in cols:
        db.execute(cur, "ALTER TABLE users ADD COLUMN auth_provider TEXT NOT NULL DEFAULT 'local'")
    db.execute(cur, "UPDATE users SET plan='free' WHERE plan IS NULL OR TRIM(plan)=''")
    db.execute(cur, "UPDATE users SET premium_since=0 WHERE premium_since IS NULL")
    db.execute(cur, "UPDATE users SET premium_expires_ts=0 WHERE premium_expires_ts IS NULL")
    db.execute(
        cur,
        f"""
        CREATE TABLE IF NOT EXISTS premium_requests(
            id {id_col},
            user_id INTEGER,
            user_email TEXT NOT NULL,
            upi_txn_ref TEXT NOT NULL,
            amount TEXT,
            screenshot_url TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            rejection_reason TEXT,
            created_ts INTEGER NOT NULL,
            reviewed_ts INTEGER NOT NULL DEFAULT 0,
            reviewed_by TEXT
        )
        """,
    )
    db.execute(
        cur,
        f"""
        CREATE TABLE IF NOT EXISTS user_memory(
            id {id_col},
            user_email TEXT UNIQUE NOT NULL,
            target_role TEXT,
            target_company TEXT,
            focus_area TEXT,
            updated_ts INTEGER NOT NULL
        )
        """,
    )
    db.execute(
        cur,
        f"""
        CREATE TABLE IF NOT EXISTS saved_resumes(
            id {id_col},
            user_email TEXT NOT NULL,
            title TEXT NOT NULL,
            resume_type TEXT NOT NULL,
            raw_content TEXT NOT NULL,
            target_role TEXT,
            created_ts INTEGER NOT NULL,
            updated_ts INTEGER NOT NULL
        )
        """,
    )
    conn.commit()
    conn.close()


def _ensure_interview_tables():
    conn = db.get_conn()
    cur = conn.cursor()
    id_col = db.id_pk_col()
    try:
        db.execute(cur, f"""
            CREATE TABLE IF NOT EXISTS interview_sessions(
                id {id_col},
                session_id TEXT UNIQUE NOT NULL,
                user_email TEXT NOT NULL,
                topic TEXT,
                difficulty TEXT,
                overall_score REAL,
                qa_history_json TEXT,
                chat_history_json TEXT,
                created_at INTEGER
            )
        """)
        conn.commit()
    except Exception:
        conn.rollback()

    try:
        cols = db.list_columns(conn, "interview_sessions")
        if "chat_history_json" not in cols:
            db.execute(cur, "ALTER TABLE interview_sessions ADD COLUMN chat_history_json TEXT")
            conn.commit()
    except Exception:
        conn.rollback()

    try:
        db.execute(cur, f"""
            CREATE TABLE IF NOT EXISTS user_cheatsheets(
                id {id_col},
                user_email TEXT NOT NULL,
                tech_name TEXT NOT NULL,
                is_custom INTEGER DEFAULT 0,
                revised_indices_json TEXT DEFAULT '[]',
                cheatsheet_json TEXT NOT NULL,
                created_ts INTEGER NOT NULL,
                updated_ts INTEGER NOT NULL
            )
        """)
        conn.commit()
    except Exception:
        conn.rollback()

    try:
        db.execute(cur, "CREATE INDEX IF NOT EXISTS idx_user_cheatsheets ON user_cheatsheets(user_email, tech_name)")
        conn.commit()
    except Exception:
        conn.rollback()

    conn.close()


_cheatsheet_table_initialized = False

def ensure_user_cheatsheets_table() -> None:
    global _cheatsheet_table_initialized
    if _cheatsheet_table_initialized:
        return
    conn = db.get_conn()
    cur = conn.cursor()
    id_col = db.id_pk_col()
    try:
        db.execute(cur, f"""
            CREATE TABLE IF NOT EXISTS user_cheatsheets(
                id {id_col},
                user_email TEXT NOT NULL,
                tech_name TEXT NOT NULL,
                is_custom INTEGER DEFAULT 0,
                revised_indices_json TEXT DEFAULT '[]',
                cheatsheet_json TEXT NOT NULL,
                created_ts INTEGER NOT NULL,
                updated_ts INTEGER NOT NULL
            )
        """)
        conn.commit()
        try:
            db.execute(cur, "CREATE INDEX IF NOT EXISTS idx_user_cheatsheets ON user_cheatsheets(user_email, tech_name)")
            conn.commit()
        except Exception:
            conn.rollback()
        _cheatsheet_table_initialized = True
    except Exception as exc:
        conn.rollback()
        logger.warning("ensure_user_cheatsheets_table deferred: %s", exc)
    finally:
        conn.close()


def get_user_cheatsheets(user_email: str) -> list:
    email = (user_email or "").strip().lower()
    if not email:
        return []
    ensure_user_cheatsheets_table()
    conn = db.get_conn()
    cur = conn.cursor()
    try:
        db.execute(cur, """
            SELECT tech_name, is_custom, revised_indices_json, cheatsheet_json, updated_ts
            FROM user_cheatsheets
            WHERE user_email=?
            ORDER BY is_custom ASC, updated_ts DESC
        """, (email,))
        rows = cur.fetchall()
    except Exception as exc:
        conn.rollback()
        logger.warning("get_user_cheatsheets query fallback: %s", exc)
        rows = []
    finally:
        conn.close()

    results = []
    for row in rows:
        try:
            revised = json.loads(row[2] or "[]")
        except Exception:
            revised = []
        try:
            data = json.loads(row[3] or "{}")
        except Exception:
            data = {}
        results.append({
            "tech_name": row[0],
            "is_custom": bool(row[1]),
            "revised_indices": revised,
            "cheatsheet": data,
            "updated_ts": row[4],
        })
    return results


def save_user_cheatsheet(user_email: str, tech_name: str, cheatsheet_data: dict, is_custom: bool = False, revised_indices: list = None) -> None:
    email = (user_email or "").strip().lower()
    t_name = (tech_name or "").strip()
    if not email or not t_name:
        return
    ensure_user_cheatsheets_table()
    conn = db.get_conn()
    cur = conn.cursor()
    now = int(time.time())
    revised_json = json.dumps(revised_indices or [])
    data_json = json.dumps(cheatsheet_data or {})
    try:
        db.execute(cur, "SELECT id FROM user_cheatsheets WHERE user_email=? AND LOWER(tech_name)=LOWER(?)", (email, t_name))
        row = cur.fetchone()
        if row:
            db.execute(cur, """
                UPDATE user_cheatsheets
                SET cheatsheet_json=?, revised_indices_json=?, updated_ts=?
                WHERE id=?
            """, (data_json, revised_json, now, row[0]))
        else:
            db.execute(cur, """
                INSERT INTO user_cheatsheets (user_email, tech_name, is_custom, revised_indices_json, cheatsheet_json, created_ts, updated_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (email, t_name, 1 if is_custom else 0, revised_json, data_json, now, now))
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.warning("save_user_cheatsheet failed: %s", exc)
    finally:
        conn.close()


def update_cheatsheet_revised(user_email: str, tech_name: str, revised_indices: list) -> None:
    email = (user_email or "").strip().lower()
    t_name = (tech_name or "").strip()
    if not email or not t_name:
        return
    ensure_user_cheatsheets_table()
    conn = db.get_conn()
    cur = conn.cursor()
    now = int(time.time())
    revised_json = json.dumps(revised_indices or [])
    try:
        db.execute(cur, """
            UPDATE user_cheatsheets
            SET revised_indices_json=?, updated_ts=?
            WHERE user_email=? AND LOWER(tech_name)=LOWER(?)
        """, (revised_json, now, email, t_name))
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.warning("update_cheatsheet_revised failed: %s", exc)
    finally:
        conn.close()


def delete_user_cheatsheet(user_email: str, tech_name: str) -> None:
    email = (user_email or "").strip().lower()
    t_name = (tech_name or "").strip()
    if not email or not t_name:
        return
    ensure_user_cheatsheets_table()
    conn = db.get_conn()
    cur = conn.cursor()
    try:
        db.execute(cur, "DELETE FROM user_cheatsheets WHERE user_email=? AND LOWER(tech_name)=LOWER(?)", (email, t_name))
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.warning("delete_user_cheatsheet failed: %s", exc)
    finally:
        conn.close()


def save_resume_report_for_user(user_email: str, report: dict, target_role: str = "") -> None:
    email = (user_email or "").strip().lower()
    if not email:
        return
    scores = report.get("scores", {}) if isinstance(report, dict) else {}
    conn = db.get_conn()
    cur = conn.cursor()
    params = (
        email,
        target_role or "",
        float(scores.get("Overall", 0) or 0),
        float(scores.get("ATS", 0) or 0),
        float(report.get("keyword_coverage", 0) or 0),
        str(scores.get("Status", "") or ""),
        json.dumps(report),
        int(time.time()),
    )
    query = """
        INSERT INTO resume_reports(
            user_email,target_role,overall,ats,keyword_coverage,status,report_json,created_ts
        ) VALUES(?,?,?,?,?,?,?,?)
    """
    try:
        db.execute(cur, query, params)
        conn.commit()
    except Exception:
        conn.rollback()
        if db.is_postgres():
            try:
                cur.execute("SELECT pg_get_serial_sequence('resume_reports', 'id')")
                seq_row = cur.fetchone()
                if seq_row and seq_row[0]:
                    seq_name = seq_row[0]
                    cur.execute('SELECT COALESCE(MAX(id), 0) + 1 FROM "resume_reports"')
                    next_id = int(cur.fetchone()[0])
                    cur.execute("SELECT setval(%s, %s, false)", (seq_name, next_id))
                db.execute(cur, query, params)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        else:
            raise
    finally:
        conn.close()


def get_latest_resume_report_for_user(user_email: str):
    email = (user_email or "").strip().lower()
    if not email:
        return None
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, 
        "SELECT report_json FROM resume_reports WHERE user_email=? ORDER BY created_ts DESC, id DESC LIMIT 1",
        (email,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    try:
        return json.loads(row[0] or "{}")
    except Exception:
        return None


def get_recent_resume_runs_for_user(user_email: str, limit: int = 10):
    email = (user_email or "").strip().lower()
    if not email:
        return []
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, 
        """
        SELECT id, created_ts, overall, ats, keyword_coverage, status, target_role
        FROM resume_reports
        WHERE user_email=?
        ORDER BY created_ts ASC, id ASC
        LIMIT ?
        """,
        (email, max(1, int(limit))),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": int(r[0] or 0),
            "timestamp": int(r[1] or 0),
            "overall": float(r[2] or 0),
            "ats": float(r[3] or 0),
            "keyword_coverage": float(r[4] or 0),
            "status": str(r[5] or ""),
            "target_role": str(r[6] or ""),
        }
        for r in rows
    ]


def get_resume_report_by_id_for_user(report_id: int, user_email: str):
    email = (user_email or "").strip().lower()
    if not email:
        return None
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, 
        "SELECT report_json, target_role FROM resume_reports WHERE id=? AND user_email=?",
        (int(report_id), email),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    try:
        report = json.loads(row[0] or "{}")
        if isinstance(report, dict):
            report["target_role"] = str(row[1] or "")
        return report
    except Exception:
        return None


def update_resume_report_json(report_id: int, user_email: str, updated_json: dict) -> bool:
    email = (user_email or "").strip().lower()
    if not email:
        return False
    conn = db.get_conn()
    cur = conn.cursor()
    try:
        db.execute(cur, 
            "UPDATE resume_reports SET report_json=? WHERE id=? AND user_email=?",
            (json.dumps(updated_json), int(report_id), email)
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update report_json for {report_id}: {e}")
        return False
    finally:
        conn.close()


_cached_sample_resume_id = None


def seed_default_sample_resume() -> int:
    global _cached_sample_resume_id
    if _cached_sample_resume_id:
        return _cached_sample_resume_id
    try:
        conn = db.get_conn()
        cur = conn.cursor()
        db.execute(cur, "SELECT id FROM saved_resumes WHERE user_email = 'athulariga12@gmail.com' LIMIT 1")
        row = cur.fetchone()
        if not row:
            now = int(time.time())
            db.execute(
                cur,
                """
                INSERT INTO saved_resumes (user_email, title, resume_type, raw_content, target_role, created_ts, updated_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "athulariga12@gmail.com",
                    "Athul Ariga - Data Engineer & Python Developer (LaTeX)",
                    "latex",
                    DEFAULT_ATHUL_RESUME,
                    "Data Engineer & Python Developer",
                    now,
                    now,
                )
            )
            sample_id = getattr(cur, "lastrowid", 1)
            conn.commit()
            conn.close()
            _cached_sample_resume_id = sample_id
            return sample_id
        conn.close()
        _cached_sample_resume_id = row[0]
        return row[0]
    except Exception as e:
        logger.warning("seed_default_sample_resume_failed err=%s", str(e))
        return 1


def save_user_resume(user_email: str, title: str, resume_type: str, raw_content: str, target_role: str = "") -> int:
    email = (user_email or "").strip().lower()
    if not email or not raw_content.strip():
        return 0
    t = (title or target_role or "My Resume").strip()[:80]
    now = int(time.time())
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        INSERT INTO saved_resumes (user_email, title, resume_type, raw_content, target_role, created_ts, updated_ts)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (email, t, resume_type, raw_content, target_role.strip(), now, now)
    )
    last_id = getattr(cur, "lastrowid", 0)
    conn.commit()
    conn.close()
    return last_id


def get_user_saved_resumes(user_email: str) -> list:
    email = (user_email or "").strip().lower()
    if not email:
        return []
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        SELECT id, title, resume_type, raw_content, target_role, created_ts
        FROM saved_resumes
        WHERE user_email = ?
        ORDER BY created_ts DESC
        """,
        (email,)
    )
    rows = cur.fetchall()
    conn.close()
    res = []
    for r in rows:
        res.append({
            "id": r[0],
            "title": r[1],
            "resume_type": r[2],
            "raw_content": r[3],
            "target_role": r[4] or "",
            "created_ts": r[5]
        })
    return res


def get_saved_resume_by_id(resume_id: int, user_email: str) -> dict:
    email = (user_email or "").strip().lower()
    conn = db.get_conn()
    cur = conn.cursor()
    if email:
        db.execute(
            cur,
            """
            SELECT id, title, resume_type, raw_content, target_role, created_ts
            FROM saved_resumes
            WHERE id = ? AND (user_email = ? OR user_email = 'athulariga12@gmail.com')
            """,
            (int(resume_id), email)
        )
    else:
        db.execute(
            cur,
            """
            SELECT id, title, resume_type, raw_content, target_role, created_ts
            FROM saved_resumes
            WHERE id = ?
            """,
            (int(resume_id),)
        )
    r = cur.fetchone()
    conn.close()
    if not r:
        if resume_id == 1 or not email:
            return {
                "id": 1,
                "title": "Athul Ariga - Data Engineer & Python Developer (LaTeX)",
                "resume_type": "latex",
                "raw_content": DEFAULT_ATHUL_RESUME,
                "target_role": "Data Engineer & Python Developer",
                "created_ts": int(time.time()),
            }
        return None
    return {
        "id": r[0],
        "title": r[1],
        "resume_type": r[2],
        "raw_content": r[3],
        "target_role": r[4] or "",
        "created_ts": r[5]
    }


def delete_user_saved_resume(resume_id: int, user_email: str) -> bool:
    email = (user_email or "").strip().lower()
    if not email:
        return False
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(
        cur,
        "DELETE FROM saved_resumes WHERE id = ? AND user_email = ?",
        (int(resume_id), email)
    )
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_user_weaknesses(user_email: str) -> list[str]:
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, "SELECT qa_history_json FROM interview_sessions WHERE user_email=?", (user_email,))
    rows = cur.fetchall()
    conn.close()
    weaknesses = set()
    for row in rows:
        try:
            hist = json.loads(row[0])
            for item in hist:
                if item.get("score", 10) < 6.0:
                    fb = item.get("feedback")
                    if fb:
                        weaknesses.add(fb[:100] + "...")
        except Exception:
            pass
    return list(weaknesses)[:3]


def get_user_memory(user_email: str, conn=None) -> dict:
    email = (user_email or "").strip().lower()
    if not email:
        return {"target_role": "", "target_company": "", "focus_area": ""}
    close_after = False
    if conn is None:
        conn = db.get_conn()
        close_after = True
    cur = conn.cursor()
    try:
        db.execute(
            cur,
            "SELECT target_role,target_company,focus_area FROM user_memory WHERE user_email=?",
            (email,),
        )
        row = cur.fetchone()
    finally:
        if close_after:
            conn.close()
    if not row:
        return {"target_role": "", "target_company": "", "focus_area": ""}
    raw_role = str(row[0] or "")
    clean_role = re.sub(r'(Developer|Engineer|Architect|Designer|Manager)\1+', r'\1', raw_role, flags=re.IGNORECASE)
    return {
        "target_role": clean_role,
        "target_company": str(row[1] or ""),
        "focus_area": str(row[2] or ""),
    }


def save_user_memory(user_email: str, target_role: str, target_company: str, focus_area: str) -> None:
    email = (user_email or "").strip().lower()
    if not email:
        return
    clean_role = re.sub(r'(Developer|Engineer|Architect|Designer|Manager)\1+', r'\1', (target_role or "").strip(), flags=re.IGNORECASE)
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        INSERT INTO user_memory(user_email,target_role,target_company,focus_area,updated_ts)
        VALUES(?,?,?,?,?)
        ON CONFLICT(user_email) DO UPDATE SET
            target_role=excluded.target_role,
            target_company=excluded.target_company,
            focus_area=excluded.focus_area,
            updated_ts=excluded.updated_ts
        """,
        (email, clean_role[:120], (target_company or "").strip()[:120], (focus_area or "").strip()[:120], int(time.time())),
    )
    conn.commit()
    conn.close()


def user_progress_summary(user_email: str, conn=None) -> dict:
    empty_progress = {
        "resume_runs_7d": 0,
        "resume_avg_7d": 0.0,
        "coding_submissions_7d": 0,
        "coding_accept_rate_7d": 0.0,
        "active_days_7d": 0,
        "current_streak_days": 0,
        "next_action": "Run your first resume review (8 min).",
    }
    email = (user_email or "").strip().lower()
    if not email:
        return dict(empty_progress)
    now_ts = int(time.time())
    seven_days_ago = now_ts - (7 * 24 * 60 * 60)
    thirty_days_ago = now_ts - (30 * 24 * 60 * 60)
    close_after = False
    if conn is None:
        conn = db.get_conn()
        close_after = True
    try:
        cur = conn.cursor()
        db.execute(
            cur,
            "SELECT COUNT(*), COALESCE(AVG(overall),0) FROM resume_reports WHERE user_email=? AND created_ts>=?",
            (email, seven_days_ago),
        )
        resume_row = cur.fetchone() or (0, 0)
        coding_ts_col = submission_ts_column(conn)
        if coding_ts_col == "created_ts":
            db.execute(
                cur,
                "SELECT COUNT(*), COALESCE(AVG(CASE WHEN status='Accepted' THEN 100.0 ELSE 0 END),0) FROM coding_submissions WHERE user_email=? AND created_ts>=?",
                (email, seven_days_ago),
            )
            coding_row = cur.fetchone() or (0, 0)
        elif coding_ts_col == "ts":
            db.execute(
                cur,
                "SELECT COUNT(*), COALESCE(AVG(CASE WHEN status='Accepted' THEN 100.0 ELSE 0 END),0) FROM coding_submissions WHERE user_email=? AND ts>=?",
                (email, seven_days_ago),
            )
            coding_row = cur.fetchone() or (0, 0)
        else:
            coding_row = (0, 0)
        db.execute(
            cur,
            "SELECT created_ts FROM resume_reports WHERE user_email=? AND created_ts>=?",
            (email, thirty_days_ago),
        )
        resume_days_rows = cur.fetchall() or []
        if coding_ts_col == "created_ts":
            db.execute(
                cur,
                "SELECT created_ts FROM coding_submissions WHERE user_email=? AND created_ts>=?",
                (email, thirty_days_ago),
            )
            coding_days_rows = cur.fetchall() or []
        elif coding_ts_col == "ts":
            db.execute(
                cur,
                "SELECT ts FROM coding_submissions WHERE user_email=? AND ts>=?",
                (email, thirty_days_ago),
            )
            coding_days_rows = cur.fetchall() or []
        else:
            coding_days_rows = []
        db.execute(
            cur,
            "SELECT ts FROM user_events WHERE user_id=? AND ts>=?",
            (email, thirty_days_ago),
        )
        events_days_rows = cur.fetchall() or []
    except Exception as progress_error:
        logger.warning("progress_summary_failed user=%s err=%s", email, str(progress_error))
        return dict(empty_progress)
    finally:
        if close_after:
            conn.close()

    resume_runs = int(resume_row[0] or 0)
    resume_avg = round(float(resume_row[1] or 0), 1)
    coding_subs = int(coding_row[0] or 0)
    coding_accept = round(float(coding_row[1] or 0), 1)
    active_days = set()
    for row in resume_days_rows:
        try:
            ts = int(row[0] or 0)
            if ts > 0:
                active_days.add(time.strftime("%Y-%m-%d", time.localtime(ts)))
        except Exception:
            continue
    for row in coding_days_rows:
        try:
            ts = int(row[0] or 0)
            if ts > 0:
                active_days.add(time.strftime("%Y-%m-%d", time.localtime(ts)))
        except Exception:
            continue
    for row in events_days_rows:
        try:
            ts = int(row[0] or 0)
            if ts > 0:
                active_days.add(time.strftime("%Y-%m-%d", time.localtime(ts)))
        except Exception:
            continue

    active_days_7d = 0
    current_streak_days = 0
    day_cursor = now_ts
    for _ in range(7):
        day_key = time.strftime("%Y-%m-%d", time.localtime(day_cursor))
        if day_key in active_days:
            active_days_7d += 1
        day_cursor -= 24 * 60 * 60

    day_cursor = now_ts
    for _ in range(31):
        day_key = time.strftime("%Y-%m-%d", time.localtime(day_cursor))
        if day_key in active_days:
            current_streak_days += 1
            day_cursor -= 24 * 60 * 60
            continue
        break

    if resume_runs == 0:
        next_action = "Run one resume review for your target role (8 min)."
    elif coding_subs < 3:
        next_action = "Submit one coding problem to improve interview readiness (12 min)."
    elif coding_accept < 60:
        next_action = "Practice one Easy coding problem and focus on edge cases (12 min)."
    else:
        next_action = "Run a 3-round mock interview and apply one improvement point (10 min)."

    return {
        "resume_runs_7d": resume_runs,
        "resume_avg_7d": resume_avg,
        "coding_submissions_7d": coding_subs,
        "coding_accept_rate_7d": coding_accept,
        "active_days_7d": active_days_7d,
        "current_streak_days": current_streak_days,
        "next_action": next_action,
    }


def safe_user_progress_summary(user_email: str) -> dict:
    try:
        return user_progress_summary(user_email)
    except Exception as progress_error:
        logger.warning("safe_progress_summary_failed user=%s err=%s", (user_email or "").strip().lower(), str(progress_error))
        return {
            "resume_runs_7d": 0,
            "resume_avg_7d": 0.0,
            "coding_submissions_7d": 0,
            "coding_accept_rate_7d": 0.0,
            "active_days_7d": 0,
            "current_streak_days": 0,
            "next_action": "Run your first resume review (8 min).",
        }


def resume_quota_state(request: Request) -> dict:
    plan = current_user_plan(request)
    if plan == "premium":
        return {"plan": plan, "is_premium": True, "limit": 0, "used": 0, "remaining": 999}
    day_key = time.strftime("%Y-%m-%d")
    used_day = request.session.get("resume_day")
    used_count = int(request.session.get("resume_count", 0) or 0)
    if used_day != day_key:
        used_day = day_key
        used_count = 0
        request.session["resume_day"] = used_day
        request.session["resume_count"] = used_count
    remaining = max(0, FREE_RESUME_DAILY_LIMIT - used_count)
    return {"plan": plan, "is_premium": False, "limit": FREE_RESUME_DAILY_LIMIT, "used": used_count, "remaining": remaining}


def consume_resume_quota(request: Request) -> None:
    state = resume_quota_state(request)
    if state.get("is_premium"):
        return
    request.session["resume_count"] = int(state.get("used", 0)) + 1
