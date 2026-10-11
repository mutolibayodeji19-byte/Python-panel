from datetime import datetime, timezone

from flask import Blueprint, jsonify, abort
from flask_login import login_required, current_user

worker = Blueprint("worker", __name__, url_prefix="/worker")


@worker.route("/status", methods=["GET"])
@worker.route("/api/status", methods=["GET"])
@login_required
def status():
    if not getattr(current_user, "is_admin", False):
        abort(403)

    return jsonify(
        service="PRIME ZENITH Local Worker API",
        connected=True,
        worker_status="online",
        execution_enabled=False,
        runtime_configured=False,
        message=(
            "Local worker status API is running inside the Flask panel. "
            "Python bot execution is not configured yet."
        ),
        time=datetime.now(timezone.utc).isoformat(),
    ), 200
