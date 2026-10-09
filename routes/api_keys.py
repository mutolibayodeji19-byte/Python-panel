import secrets

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import func, case

from database.database import db
from database.api_models import APIKey, APIUsage

api_keys = Blueprint("api_keys", __name__, url_prefix="/api-keys")


@api_keys.route("/")
@login_required
def home():
    keys = APIKey.query.filter_by(
        user_id=current_user.id
    ).order_by(APIKey.id.desc()).all()

    stats = {}
    if keys:
        key_ids = [key.id for key in keys]
        rows = (
            db.session.query(
                APIUsage.api_key_id,
                func.count(APIUsage.id).label("total"),
                func.sum(case((APIUsage.status_code == 200, 1), else_=0)).label("successes"),
                func.sum(case((APIUsage.status_code != 200, 1), else_=0)).label("failures"),
            )
            .filter(APIUsage.api_key_id.in_(key_ids))
            .group_by(APIUsage.api_key_id)
            .all()
        )
        stats = {
            row.api_key_id: {
                "total": int(row.total or 0),
                "successes": int(row.successes or 0),
                "failures": int(row.failures or 0),
            }
            for row in rows
        }

    return render_template("api_keys.html", keys=keys, stats=stats)


@api_keys.route("/create", methods=["POST"])
@login_required
def create():
    name = request.form.get("name", "Default").strip()[:80] or "Default"
    key = "ZNT_" + secrets.token_urlsafe(24)

    api_key = APIKey(
        key=key,
        user_id=current_user.id,
        name=name
    )

    db.session.add(api_key)
    db.session.commit()
    flash("API key created successfully.", "success")
    return redirect(url_for("api_keys.home"))


@api_keys.route("/rename/<int:key_id>", methods=["POST"])
@login_required
def rename(key_id):
    api_key = APIKey.query.filter_by(
        id=key_id,
        user_id=current_user.id
    ).first_or_404()

    name = request.form.get("name", "").strip()
    if not name:
        flash("Key name cannot be empty.", "error")
    else:
        api_key.name = name[:80]
        db.session.commit()
        flash("API key renamed successfully.", "success")

    return redirect(url_for("api_keys.home"))


@api_keys.route("/revoke/<int:key_id>", methods=["POST"])
@login_required
def revoke(key_id):
    api_key = APIKey.query.filter_by(
        id=key_id,
        user_id=current_user.id
    ).first_or_404()

    api_key.is_active = False
    db.session.commit()
    flash("API key revoked successfully.", "success")
    return redirect(url_for("api_keys.home"))
