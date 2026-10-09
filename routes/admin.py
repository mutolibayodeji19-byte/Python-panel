from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from database.database import db
from sqlalchemy import func
from database.models import User
from database.api_models import APIKey, APIUsage


admin = Blueprint("admin", __name__, url_prefix="/admin")


@admin.before_request
def admin_required():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))

    if not current_user.is_admin:
        return "Access denied — Admins only.", 403


@admin.route("/")
@login_required
def home():
    users = User.query.order_by(User.id.desc()).all()

    return render_template(
        "admin.html",
        users=users
    )


@admin.route("/user/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def edit_user(user_id):
    user = db.session.get(User, user_id)

    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin.home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        is_admin = request.form.get("is_admin") == "on"
        is_active = request.form.get("is_active") == "on"
        password = request.form.get("password", "")
        expires_at_raw = request.form.get("expires_at", "").strip()
        plan = request.form.get("plan", "FREE").strip().upper()

        if not username or not email:
            flash("Username and email are required.", "error")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        existing_username = User.query.filter(
            User.username == username,
            User.id != user.id
        ).first()

        if existing_username:
            flash("Username already exists.", "error")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        existing_email = User.query.filter(
            User.email == email,
            User.id != user.id
        ).first()

        if existing_email:
            flash("Email already exists.", "error")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        # Never allow the owner to disable or remove their own admin access.
        if user.id == current_user.id:
            is_admin = True
            is_active = True

        user.username = username
        user.email = email
        user.is_admin = is_admin
        user.is_active_user = is_active
        user.plan = plan

        if password:
            user.set_password(password)

        if expires_at_raw:
            from datetime import datetime
            user.expires_at = datetime.strptime(expires_at_raw, "%Y-%m-%dT%H:%M")
        else:
            user.expires_at = None

        db.session.commit()

        flash(f"{user.username} updated successfully.", "success")

        return redirect(url_for("admin.home"))

    return render_template(
        "edit_user.html",
        user=user
    )


@admin.route("/user/<int:user_id>/toggle", methods=["POST"])
@login_required
def toggle_user(user_id):
    user = db.session.get(User, user_id)

    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin.home"))

    if user.id == current_user.id:
        flash("You cannot disable your own account.", "error")
        return redirect(url_for("admin.home"))

    user.is_active_user = not user.is_active_user
    db.session.commit()

    status = "activated" if user.is_active_user else "disabled"

    flash(f"{user.username} has been {status}.", "success")

    return redirect(url_for("admin.home"))


@admin.route("/user/<int:user_id>/delete", methods=["POST"])
@login_required
def delete_user(user_id):
    user = db.session.get(User, user_id)

    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin.home"))

    if user.id == current_user.id:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin.home"))

    db.session.delete(user)
    db.session.commit()

    flash(f"{user.username} has been deleted.", "success")

    return redirect(url_for("admin.home"))


@admin.route("/api-keys")
@login_required
def api_keys_page():
    key_rows = (
        db.session.query(APIKey, User)
        .join(User, APIKey.user_id == User.id)
        .order_by(APIKey.id.desc())
        .all()
    )

    usage_counts = dict(
        db.session.query(APIUsage.api_key_id, func.count(APIUsage.id))
        .group_by(APIUsage.api_key_id)
        .all()
    )

    return render_template(
        "admin_api_keys.html",
        key_rows=key_rows,
        usage_counts=usage_counts
    )


@admin.route("/statistics")
@login_required
def statistics_page():
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active_user=True).count()
    total_keys = APIKey.query.count()
    active_keys = APIKey.query.filter_by(is_active=True).count()
    total_requests = APIUsage.query.count()
    failed_requests = APIUsage.query.filter(APIUsage.status_code != 200).count()

    recent_rows = (
        db.session.query(APIUsage, APIKey, User)
        .join(APIKey, APIUsage.api_key_id == APIKey.id)
        .join(User, APIKey.user_id == User.id)
        .order_by(APIUsage.created_at.desc(), APIUsage.id.desc())
        .limit(20)
        .all()
    )

    return render_template(
        "admin_statistics.html",
        total_users=total_users,
        active_users=active_users,
        total_keys=total_keys,
        active_keys=active_keys,
        total_requests=total_requests,
        failed_requests=failed_requests,
        recent_rows=recent_rows
    )
