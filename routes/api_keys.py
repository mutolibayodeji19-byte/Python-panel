import secrets

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from database.database import db
from database.api_models import APIKey


api_keys = Blueprint(
    "api_keys",
    __name__,
    url_prefix="/api-keys"
)


@api_keys.route("/")
@login_required
def home():
    keys = APIKey.query.filter_by(
        user_id=current_user.id
    ).order_by(APIKey.id.desc()).all()

    return render_template(
        "api_keys.html",
        keys=keys
    )


@api_keys.route("/create", methods=["POST"])
@login_required
def create():
    key = "ZNT_" + secrets.token_urlsafe(24)

    api_key = APIKey(
        key=key,
        user_id=current_user.id,
        name="Default"
    )

    db.session.add(api_key)
    db.session.commit()

    flash("API key created successfully.", "success")

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
