from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user

from database.database import db
from database.models import User


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
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("register.html")

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "error")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("Email already exists.", "error")
            return render_template("register.html")

        user = User(
            username=username,
            email=email
        )

        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash("Account created. You can now log in.", "success")

        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
