from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template
from flask_login import login_required, current_user

from database.api_models import APIKey, APIUsage


dashboard = Blueprint("dashboard", __name__)


def daily_limit_for(user):
    plan = (user.plan or "FREE").upper()

    limits = {
        "OWNER": None,
        "ADMIN": None,
        "PRO": 5000,
        "PREMIUM": 1000,
        "PAID": 1000,
        "FREE": 100,
    }

    return limits.get(plan, 100)


@dashboard.route("/")
@login_required
def home():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    since = now - timedelta(hours=24)

    keys = APIKey.query.filter_by(user_id=current_user.id).all()
    key_ids = [key.id for key in keys]

    usage_query = APIUsage.query.filter(
        APIUsage.api_key_id.in_(key_ids),
        APIUsage.created_at >= since,
        APIUsage.status_code == 200
    )

    used = usage_query.count()
    limit = daily_limit_for(current_user)
    remaining = None if limit is None else max(limit - used, 0)

    recent_usage = (
        APIUsage.query
        .filter(APIUsage.api_key_id.in_(key_ids))
        .order_by(APIUsage.id.desc())
        .limit(10)
        .all()
    ) if key_ids else []

    return render_template(
        "dashboard.html",
        user=current_user,
        api_used=used,
        api_limit=limit,
        api_remaining=remaining,
        api_key_count=len(keys),
        recent_api_usage=recent_usage
    )
