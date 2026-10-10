from datetime import datetime, timedelta
import secrets

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from database.database import db
from database.models import User
from database.control_access_models import ControlAccessRequest

control_access = Blueprint("control_access", __name__, url_prefix="/control-access")


def owner_only():
    return (
        current_user.is_authenticated
        and current_user.is_admin
        and current_user.plan == "OWNER"
    )


@control_access.route("/request", methods=["GET", "POST"])
@login_required
def request_access():
    now = datetime.utcnow()

    latest = (
        ControlAccessRequest.query
        .filter_by(user_id=current_user.id)
        .order_by(ControlAccessRequest.id.desc())
        .first()
    )

    if request.method == "POST":
        if latest and latest.status == "pending":
            flash("Your request is already awaiting owner approval.", "info")
        elif (
            latest
            and latest.status == "approved"
            and latest.access_expires_at
            and latest.access_expires_at > now
        ):
            flash("You already have active temporary access.", "info")
        else:
            db.session.add(ControlAccessRequest(user_id=current_user.id))
            db.session.commit()
            flash("Access request sent to the owner.", "success")

        return redirect(url_for("control_access.request_access"))

    return render_template("control_access_request.html", latest=latest)


@control_access.route("/owner")
@login_required
def owner_requests():
    if not owner_only():
        return "Owner access required.", 403

    rows = (
        db.session.query(ControlAccessRequest, User)
        .join(User, ControlAccessRequest.user_id == User.id)
        .order_by(ControlAccessRequest.id.desc())
        .all()
    )
    return render_template("control_access_owner.html", rows=rows, now=datetime.utcnow())


@control_access.route("/owner/<int:request_id>/approve", methods=["POST"])
@login_required
def approve_request(request_id):
    if not owner_only():
        return "Owner access required.", 403

    item = db.session.get(ControlAccessRequest, request_id)
    if not item or item.status != "pending":
        flash("Request not found or already reviewed.", "error")
        return redirect(url_for("control_access.owner_requests"))

    passkey = secrets.token_urlsafe(24)
    now = datetime.utcnow()

    item.status = "approved"
    item.reviewed_at = now
    item.reviewed_by_id = current_user.id
    item.passkey_hash = generate_password_hash(passkey)
    item.passkey_expires_at = now + timedelta(hours=24)
    item.passkey_used_at = None
    item.access_expires_at = None

    db.session.commit()

    flash(
        f"Give this passkey ONLY to {User.query.get(item.user_id).username}: "
        f"{passkey} — valid for 24 hours and one use.",
        "success"
    )
    return redirect(url_for("control_access.owner_requests"))


@control_access.route("/owner/<int:request_id>/reject", methods=["POST"])
@login_required
def reject_request(request_id):
    if not owner_only():
        return "Owner access required.", 403

    item = db.session.get(ControlAccessRequest, request_id)
    if not item or item.status != "pending":
        flash("Request not found or already reviewed.", "error")
    else:
        item.status = "rejected"
        item.reviewed_at = datetime.utcnow()
        item.reviewed_by_id = current_user.id
        db.session.commit()
        flash("Access request rejected.", "success")

    return redirect(url_for("control_access.owner_requests"))


@control_access.route("/redeem", methods=["GET", "POST"])
@login_required
def redeem_passkey():
    if request.method == "POST":
        supplied = request.form.get("passkey", "").strip()
        now = datetime.utcnow()

        candidates = (
            ControlAccessRequest.query
            .filter_by(
                user_id=current_user.id,
                status="approved",
                passkey_used_at=None
            )
            .all()
        )

        for item in candidates:
            if (
                item.passkey_hash
                and item.passkey_expires_at
                and item.passkey_expires_at > now
                and check_password_hash(item.passkey_hash, supplied)
            ):
                item.passkey_used_at = now
                item.access_expires_at = now + timedelta(hours=24)
                db.session.commit()
                flash("Passkey accepted. Temporary Control Center access is active for 24 hours.", "success")
                return redirect(url_for("control_access.temporary_center"))

        flash("Invalid, expired, or already-used passkey.", "error")

    return render_template("control_access_redeem.html")


@control_access.route("/owner/<int:request_id>/revoke", methods=["POST"])
@login_required
def revoke_access(request_id):
    if not owner_only():
        return "Owner access required.", 403

    item = db.session.get(ControlAccessRequest, request_id)

    if not item or item.status != "approved":
        flash("Active approval not found.", "error")
    else:
        item.status = "revoked"
        item.access_expires_at = datetime.utcnow()
        db.session.commit()
        flash("Temporary access revoked.", "success")

    return redirect(url_for("control_access.owner_requests"))


@control_access.route("/center")
@login_required
def temporary_center():
    if current_user.is_admin:
        return render_template("control_access_center.html", grant=None)

    grant = ControlAccessRequest.query.filter(
        ControlAccessRequest.user_id == current_user.id,
        ControlAccessRequest.status == "approved",
        ControlAccessRequest.access_expires_at > datetime.utcnow()
    ).first()

    if not grant:
        flash("Your temporary access is expired or revoked.", "error")
        return redirect(url_for("control_access.request_access"))

    return render_template("control_access_center.html", grant=grant)
