from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import func, case

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
    # Keep the existing rolling 24-hour quota definition:
    # only HTTP 200 responses count toward the limit.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    since = now - timedelta(hours=24)
    chart_start = now.date() - timedelta(days=6)

    keys = APIKey.query.filter_by(user_id=current_user.id).all()
    key_ids = [key.id for key in keys]

    limit = daily_limit_for(current_user)

    if key_ids:
        last_day = APIUsage.query.filter(
            APIUsage.api_key_id.in_(key_ids),
            APIUsage.created_at >= since
        )
        api_used = last_day.filter(APIUsage.status_code == 200).count()
        api_failed = last_day.filter(APIUsage.status_code != 200).count()
        api_total_24h = last_day.count()

        recent_api_usage = (
            APIUsage.query
            .filter(APIUsage.api_key_id.in_(key_ids))
            .order_by(APIUsage.created_at.desc(), APIUsage.id.desc())
            .limit(25)
            .all()
        )

        # Aggregate per-key counts in SQL rather than loading every row.
        per_key_rows = (
            APIUsage.query.with_entities(
                APIUsage.api_key_id,
                func.count(APIUsage.id).label("total"),
                func.sum(
                    case((APIUsage.status_code == 200, 1), else_=0)
                ).label("successes"),
                func.sum(
                    case((APIUsage.status_code != 200, 1), else_=0)
                ).label("failures"),
                func.max(APIUsage.created_at).label("last_request")
            )
            .filter(APIUsage.api_key_id.in_(key_ids))
            .group_by(APIUsage.api_key_id)
            .all()
        )
        stats_by_key = {
            row.api_key_id: row for row in per_key_rows
        }

        chart_rows = (
            APIUsage.query.with_entities(
                func.date(APIUsage.created_at).label("day"),
                func.count(APIUsage.id).label("total"),
                func.sum(
                    case((APIUsage.status_code == 200, 1), else_=0)
                ).label("successes")
            )
            .filter(
                APIUsage.api_key_id.in_(key_ids),
                APIUsage.created_at >= datetime.combine(
                    chart_start, datetime.min.time()
                ),
                APIUsage.created_at < now + timedelta(days=1)
            )
            .group_by(func.date(APIUsage.created_at))
            .all()
        )
        chart_by_day = {
            str(row.day): {
                "total": int(row.total or 0),
                "successes": int(row.successes or 0)
            }
            for row in chart_rows
        }
    else:
        api_used = 0
        api_failed = 0
        api_total_24h = 0
        recent_api_usage = []
        stats_by_key = {}
        chart_by_day = {}

    api_remaining = (
        None if limit is None else max(limit - api_used, 0)
    )

    daily_stats = []
    for offset in range(7):
        day = chart_start + timedelta(days=offset)
        item = chart_by_day.get(day.isoformat(), {})
        daily_stats.append({
            "label": day.strftime("%a"),
            "date": day.strftime("%d %b"),
            "total": item.get("total", 0),
            "successes": item.get("successes", 0)
        })

    chart_max = max(
        (item["total"] for item in daily_stats), default=0
    )

    key_stats = []
    for key in keys:
        row = stats_by_key.get(key.id)
        total = int(row.total or 0) if row else 0
        successes = int(row.successes or 0) if row else 0
        failures = int(row.failures or 0) if row else 0
        last_request = row.last_request if row else key.last_used

        key_stats.append({
            "key": key,
            "total": total,
            "successes": successes,
            "failures": failures,
            "last_request": last_request
        })

    return render_template(
        "dashboard.html",
        user=current_user,
        api_used=api_used,
        api_limit=limit,
        api_remaining=api_remaining,
        api_key_count=len(keys),
        recent_api_usage=recent_api_usage,
        api_failed=api_failed,
        api_total_24h=api_total_24h,
        daily_stats=daily_stats,
        chart_max=chart_max,
        key_stats=key_stats
    )
