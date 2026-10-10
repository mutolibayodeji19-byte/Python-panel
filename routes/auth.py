import re
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user

from database.database import db
from database.models import User
from extensions import limiter

auth = Blueprint("auth", __name__)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password) and user.is_active_user:
            if user.expires_at and user.expires_at <= datetime.utcnow():
                flash("Your account has expired.", "error")
                return render_template("login.html")

            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user)
            return redirect(url_for("dashboard.home"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@auth.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    if request.method == "POST":
        # Honeypot: ordinary visitors should leave this field empty.
        if request.form.get("website", "").strip():
            # Do not create an account or reveal the honeypot result.
            return redirect(url_for("auth.login"))

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if (
            not 3 <= len(username) <= 30
            or not re.fullmatch(r"[A-Za-z0-9_-]+", username)
        ):
            flash(
                "Username must be 3–30 characters using letters, "
                "numbers, underscores or hyphens.",
                "error",
            )
            return render_template("register.html")

        if (
            len(email) > 120
            or not re.fullmatch(
                r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
                r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}"
                r"[A-Za-z0-9])?(?:\.[A-Za-z0-9]"
                r"(?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+",
                email,
            )
        ):
            flash("Enter a valid email address.", "error")
            return render_template("register.html")

        if not 10 <= len(password) <= 128:
            flash("Password must be between 10 and 128 characters.", "error")
            return render_template("register.html")

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "error")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("Email already exists.", "error")
            return render_template("register.html")

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("That username or email is already registered.", "error")
            return render_template("register.html")

        flash("Account created. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
