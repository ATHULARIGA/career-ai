import time
from fastapi import FastAPI, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

from services.resume.resume_parser import extract_text
from services.resume.scoring import score_resume
from services.interview.interview_engine import generate_questions, generate_follow_up, generate_lifeline_hints
from services.booking.booking_db import save_booking, get_bookings, get_booking, assign_mentor_email
from services.booking.email_sender import send_mail
from services.roadmap.mindmap_generator import generate_mindmap
from services.interview.interview_feedback import analyze_answer, hiring_decision
from services.analytics.admin_analytics import (
    init_admin_tables,
    log_event,
    log_model_health,
    add_feedback,
    update_feedback_status,
    log_audit,
    upsert_experiment,
    upsert_ab_test,
    add_safety_event,
    log_mentor_metric,
    dashboard_payload,
    export_all_json,
    export_all_csv,
)
from services.coding.coding_platform import (
    DEFAULT_PROBLEMS,
    SUPPORTED_LANGUAGES,
    get_all_problems,
    get_custom_problems,
    get_submission_stats,
    get_submission_stats_extended,
    get_problem,
    evaluate_submission,
    save_submission,
    save_attempt_timeline,
    get_user_submission_summary,
    get_problem_timeline,
    submission_ts_column,
    fetch_idempotent_response,
    store_idempotent_response,
    hint_ladder,
    review_code_heuristic,
    coding_followup_questions,
    recommend_next_problem,
    personalized_practice_queue,
    study_plan,
    interview_readiness_score,
    weak_tags_for_user,
    topic_mastery_report,
    daily_goal_progress,
    editorial_bundle,
    contest_snapshot,
    plagiarism_alerts,
    export_problems_json,
    export_problems_csv,
    import_problems_from_json,
    coverage_report,
    company_sets,
    get_company_problems,
    starter_for_language,
    init_coding_tables,
    enqueue_judge_job,
    process_judge_job,
    get_judge_job,
    add_custom_problem,
    update_custom_problem,
    delete_custom_problem,
    parse_test_lines,
)

from core.config import *
from core.security import *
from core.middleware import *
from core.database import *
from core.helpers import *
from core.app import *

# Explicitly export underscored functions that 'import *' omits
from core.database import _ensure_auth_tables, _ensure_interview_tables
from core.security import _auth_key, _same_origin
from core.helpers import (
    _timed_session_key,
    _clear_timed_mode,
    _apply_timed_mode_selection,
    _timed_mode_state,
    _mark_timed_mode_submitted,
    _solved_problem_count,
    _safe_call,
    _select_problem,
    _readiness_from_summary,
    _daily_goal_from_attempts,
    _recommended_from_problems,
    _practice_queue_from_problems,
    _light_contest_snapshot,
    _parse_problem_admin_payload,
)

