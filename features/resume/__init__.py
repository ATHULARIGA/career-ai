import time
from .scorer import score_resume
from .rewriter import generate_resume_rewrite
from .cover_letter import generate_cover_letter
from .jd_scraper import scrape_job_link, clean_scraped_jd
from .comparator import score_resume_lightweight
from db import (
    get_latest_resume_report_for_user,
    get_resume_report_by_id_for_user,
    current_user_plan,
)
from core import FREE_RESUME_DAILY_LIMIT

def resume_quota_state(request):
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

def consume_resume_quota(request) -> None:
    state = resume_quota_state(request)
    if state.get("is_premium"):
        return
    request.session["resume_count"] = int(state.get("used", 0)) + 1
