import sys
sys.path.insert(0, ".")
from packages.core.scoring import score_candidate, generate_reasoning
print("core.scoring: OK")
from packages.core.router import ModelRouter
print("core.router: OK")
from packages.core.db import Base, Recruiter, Job, Resume, Score
print("core.db: OK")
from packages.core.ingestion import ingest_file
print("core.ingestion: OK")

c = {
    "candidate_id": "CAND_0000001",
    "profile": {
        "anonymized_name": "Test", "headline": "", "summary": "",
        "location": "MH", "country": "India",
        "years_of_experience": 5.0,
        "current_title": "ML Engineer",
        "current_company": "Swiggy", "current_company_size": "501-1000",
        "current_industry": "Tech",
    },
    "career_history": [{
        "company": "Swiggy", "title": "ML Engineer",
        "start_date": "2020-01-01", "end_date": None,
        "duration_months": 60, "is_current": True,
        "industry": "Tech", "company_size": "501-1000",
        "description": "pytorch nlp ranking gradient fine-tuning bert",
    }],
    "education": [], "skills": [],
    "redrob_signals": {
        "profile_completeness_score": 80, "signup_date": "2022-01-01",
        "last_active_date": "2026-06-01", "open_to_work_flag": True,
        "profile_views_received_30d": 10, "applications_submitted_30d": 2,
        "recruiter_response_rate": 0.7, "avg_response_time_hours": 12.0,
        "skill_assessment_scores": {}, "connection_count": 200,
        "endorsements_received": 30, "notice_period_days": 30,
        "expected_salary_range_inr_lpa": {"min": 20, "max": 40},
        "preferred_work_mode": "hybrid", "willing_to_relocate": True,
        "github_activity_score": 40, "search_appearance_30d": 20,
        "saved_by_recruiters_30d": 5, "interview_completion_rate": 0.8,
        "offer_acceptance_rate": 0.7, "verified_email": True,
        "verified_phone": True, "linkedin_connected": True,
    },
}
result = score_candidate(c)
print(f"score_candidate result: {result['score']}  OK")
print("ALL IMPORTS VERIFIED")
