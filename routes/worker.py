import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from flask import Blueprint, current_app, jsonify, abort
from flask_login import login_required, current_user

worker = Blueprint("worker", __name__, url_prefix="/worker")


@worker.route("/status", methods=["GET"])
@login_required
def status():
    if not getattr(current_user, "is_admin", False):
        abort(403)

    base_url = current_app.config.get("WORKER_BASE_URL", "").rstrip("/")
    secret = current_app.config.get("WORKER_SHARED_SECRET", "")

    if not base_url or not secret:
        return jsonify(
            connected=False,
            error="Worker connection settings are missing."
        ), 503

    req = Request(
        base_url + "/api/worker/status",
        headers={"X-Worker-Secret": secret},
        method="GET",
    )

    try:
        with urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
            return jsonify(
                connected=True,
                worker_status=data.get("status", "unknown"),
                execution_enabled=data.get("execution_enabled", False),
            ), 200
    except HTTPError as exc:
        if exc.code in (401, 403):
            return jsonify(
                connected=False,
                error="Worker authentication failed. Check the shared secret."
            ), 502
        return jsonify(
            connected=False,
            error="Worker returned an HTTP error.",
            worker_http_status=exc.code,
        ), 502
    except (URLError, TimeoutError, OSError, ValueError):
        return jsonify(
            connected=False,
            error="Worker unreachable or returned invalid JSON."
        ), 502
