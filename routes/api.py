from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from database.database import db
from database.models import User
from database.api_models import APIKey, APIUsage


api = Blueprint("api", __name__, url_prefix="/api/v1")


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


@api.route("/ping", methods=["GET"])
def ping():
    supplied_key = request.headers.get("X-API-Key", "").strip()

    if not supplied_key:
        return jsonify({
            "success": False,
            "error": "Missing X-API-Key header"
        }), 401

    api_key = APIKey.query.filter_by(
        key=supplied_key,
        is_active=True
    ).first()

    if not api_key:
        return jsonify({
            "success": False,
            "error": "Invalid or revoked API key"
        }), 401

    user = db.session.get(User, api_key.user_id)

    if (
        not user
        or not user.is_active_user
        or (user.expires_at and user.expires_at <= datetime.utcnow())
    ):
        return jsonify({
            "success": False,
            "error": "Account inactive or expired"
        }), 403

    now = datetime.utcnow()
    since = now - timedelta(hours=24)
    limit = daily_limit_for(user)

    account_key_ids = db.session.query(APIKey.id).filter(
        APIKey.user_id == user.id
    )

    recent_usage = APIUsage.query.filter(
        APIUsage.api_key_id.in_(account_key_ids),
        APIUsage.created_at >= since,
        APIUsage.status_code == 200
    ).count()

    if limit is not None and recent_usage >= limit:
        return jsonify({
            "success": False,
            "error": "API usage limit reached",
            "limit": limit,
            "used": recent_usage
        }), 429

    api_key.last_used = now

    usage = APIUsage(
        api_key_id=api_key.id,
        endpoint="/api/v1/ping",
        status_code=200
    )

    db.session.add(usage)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "PRIME ZENITH API is online",
        "plan": user.plan,
        "usage_last_24_hours": recent_usage + 1,
        "limit_last_24_hours": limit
    }), 200
