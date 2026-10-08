from flask import Blueprint, render_template
from flask_login import login_required, current_user


dashboard = Blueprint("dashboard", __name__)


@dashboard.route("/")
@login_required
def home():
    return render_template(
        "dashboard.html",
        user=current_user
    )
