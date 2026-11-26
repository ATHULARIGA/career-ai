import time

from fastapi import BackgroundTasks, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)

from core.app import *
from core.config import *
from core.database import *

# Explicitly export underscored functions that 'import *' omits
from core.database import _ensure_auth_tables, _ensure_interview_tables
from core.helpers import *
from core.helpers import (
    _apply_timed_mode_selection,
    _clear_timed_mode,
    _daily_goal_from_attempts,
    _light_contest_snapshot,
    _mark_timed_mode_submitted,
    _parse_problem_admin_payload,
    _practice_queue_from_problems,
    _readiness_from_summary,
    _recommended_from_problems,
    _safe_call,
    _select_problem,
    _solved_problem_count,
    _timed_mode_state,
    _timed_session_key,
)
from core.middleware import *
from core.security import *
from core.security import _auth_key, _same_origin
from services.analytics.admin_analytics import (
    add_feedback,
    add_safety_event,
    dashboard_payload,
    export_all_csv,
    export_all_json,
    export_periodic_report_csv,
    export_periodic_report_json,
    export_visitor_traffic_csv,
    export_visitor_traffic_json,
    get_admin_users_list,
    get_periodic_report,
    get_visitor_traffic_analytics,
    init_admin_tables,
    log_audit,
    log_event,
    log_mentor_metric,
    log_model_health,
    record_visitor_traffic,
    update_feedback_status,
    update_user_role,
    upsert_ab_test,
    upsert_experiment,
)
from services.booking.booking_db import (
    assign_mentor_email,
    get_booking,
    get_bookings,
    save_booking,
)
from services.booking.email_sender import send_mail
from services.coding.coding_platform import (
    DEFAULT_PROBLEMS,
    SUPPORTED_LANGUAGES,
    add_custom_problem,
    coding_followup_questions,
    company_sets,
    contest_snapshot,
    coverage_report,
    daily_goal_progress,
    delete_custom_problem,
    editorial_bundle,
    enqueue_judge_job,
    evaluate_submission,
    export_problems_csv,
    export_problems_json,
    fetch_idempotent_response,
    get_all_problems,
    get_company_problems,
    get_custom_problems,
    get_judge_job,
    get_problem,
    get_problem_timeline,
    get_submission_stats,
    get_submission_stats_extended,
    get_user_submission_summary,
    hint_ladder,
    import_problems_from_json,
    init_coding_tables,
    interview_readiness_score,
    parse_test_lines,
    personalized_practice_queue,
    plagiarism_alerts,
    process_judge_job,
    recommend_next_problem,
    review_code_heuristic,
    save_attempt_timeline,
    save_submission,
    starter_for_language,
    store_idempotent_response,
    study_plan,
    submission_ts_column,
    topic_mastery_report,
    update_custom_problem,
    weak_tags_for_user,
)
from services.interview.interview_engine import (
    generate_follow_up,
    generate_lifeline_hints,
    generate_questions,
)
from services.interview.interview_feedback import analyze_answer, hiring_decision
from services.resume.resume_parser import extract_text
from services.resume.scoring import score_resume
from services.roadmap.mindmap_generator import generate_mindmap

