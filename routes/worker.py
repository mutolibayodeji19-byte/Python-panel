import hmac
import json
import os
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Blueprint, jsonify, abort, request
from flask_login import login_required, current_user

worker = Blueprint("worker", __name__, url_prefix="/worker")


def is_admin():
    return bool(getattr(current_user, "is_admin", False))


def worker_request(path, method="GET", payload=None):
    base_url = os.environ.get(
        "WORKER_BASE_URL", ""
    ).strip().rstrip("/")

    worker_key = os.environ.get("WORKER_KEY", "").strip()

    if not base_url.startswith("https://") or not worker_key:
        return None, {"error": "Worker configuration is incomplete."}, 503

    body = None
    headers = {
        "Accept": "application/json",
        "X-Worker-Key": worker_key,
        "User-Agent": "PRIME-ZENITH-PANEL/2.0",
    }

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(
        base_url + path,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(req, timeout=20) as response:
            raw = response.read()
            data = json.loads(raw.decode("utf-8")) if raw else {}
            return data, None, response.status

    except HTTPError as exc:
        try:
            details = json.loads(exc.read(2000).decode("utf-8"))
        except Exception:
            details = {}

        return None, {
            "error": details.get("error", "Worker request failed."),
            "worker_http_status": exc.code,
        }, exc.code

    except (URLError, TimeoutError, OSError):
        return None, {"error": "Could not reach the worker."}, 502

    except (ValueError, UnicodeDecodeError):
        return None, {"error": "Worker returned invalid JSON."}, 502


def require_admin():
    if not is_admin():
        abort(403)


def valid_identifier(identifier):
    return bool(
        identifier
        and len(identifier) <= 64
        and re.fullmatch(r"[A-Za-z0-9]+", identifier)
    )


@worker.route("/status", methods=["GET"])
@worker.route("/api/status", methods=["GET"])
@login_required
def status():
    require_admin()

    data, error, code = worker_request("/worker/status")

    if error:
        return jsonify(
            service="PRIME ZENITH Worker",
            connected=False,
            **error,
        ), code

    return jsonify(data), 200


@worker.route("/pterodactyl/status", methods=["GET"])
@login_required
def pterodactyl_status():
    require_admin()

    data, error, code = worker_request("/worker/servers")

    if error:
        return jsonify(
            service="PRIME ZENITH Pterodactyl Integration",
            connected=False,
            **error,
        ), code

    return jsonify(
        service="PRIME ZENITH Pterodactyl Integration",
        connected=True,
        execution_enabled=True,
        server_count=data.get("count", 0),
        servers=data.get("servers", []),
        time=datetime.now(timezone.utc).isoformat(),
    ), 200


@worker.route("/pterodactyl/servers/<identifier>/status", methods=["GET"])
@login_required
def server_status(identifier):
    require_admin()

    if not valid_identifier(identifier):
        abort(400)

    data, error, code = worker_request(
        f"/worker/servers/{identifier}/status"
    )

    if error:
        return jsonify(error), code

    return jsonify(data), 200


@worker.route(
    "/pterodactyl/servers/<identifier>/power",
    methods=["POST"],
)
@login_required
def server_power(identifier):
    require_admin()

    if not valid_identifier(identifier):
        abort(400)

    payload = request.get_json(silent=True) or {}
    signal = str(payload.get("signal", "")).lower()

    if signal not in {"start", "stop", "restart"}:
        return jsonify({
            "error": "Signal must be start, stop, or restart."
        }), 400

    data, error, code = worker_request(
        f"/worker/servers/{identifier}/power",
        method="POST",
        payload={"signal": signal},
    )

    if error:
        return jsonify(error), code

    return jsonify(data), 200
