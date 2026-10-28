import json
import os
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Blueprint, jsonify, abort, request, current_app
from flask_login import login_required, current_user


worker = Blueprint("worker", __name__, url_prefix="/worker")


def is_admin():
    return bool(getattr(current_user, "is_admin", False))


def require_admin():
    if not is_admin():
        abort(403)


def valid_identifier(identifier):
    return bool(
        identifier
        and len(identifier) <= 64
        and re.fullmatch(r"[A-Za-z0-9]+", identifier)
    )


def get_worker_config():
    base_url = (
        current_app.config.get("WORKER_BASE_URL")
        or os.environ.get("WORKER_BASE_URL", "")
    ).strip().rstrip("/")

    worker_key = (
        current_app.config.get("WORKER_KEY")
        or os.environ.get("WORKER_KEY", "")
    ).strip()

    return base_url, worker_key


def worker_request(path, method="GET", payload=None):
    base_url, worker_key = get_worker_config()

    if not base_url.startswith("https://"):
        return None, {
            "error": "WORKER_BASE_URL must be a valid HTTPS URL.",
            "stage": "configuration",
        }, 503

    if not worker_key:
        return None, {
            "error": "WORKER_KEY is missing.",
            "stage": "configuration",
        }, 503

    if not path.startswith("/worker/"):
        return None, {
            "error": "Invalid worker endpoint.",
            "stage": "validation",
        }, 400

    url = base_url + path

    headers = {
        "Accept": "application/json",
        "X-Worker-Key": worker_key,
        "User-Agent": "PRIME-ZENITH-PANEL/2.5",
    }

    body = None

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(req, timeout=20) as response:
            raw = response.read()

            try:
                data = json.loads(raw.decode("utf-8")) if raw else {}
            except (ValueError, UnicodeDecodeError):
                return None, {
                    "error": "Worker returned invalid JSON.",
                    "stage": "response",
                }, 502

            return data, None, response.status

    except HTTPError as exc:
        try:
            raw_error = exc.read(2000).decode("utf-8")
            details = json.loads(raw_error)
        except (ValueError, UnicodeDecodeError, OSError):
            details = {}

        return None, {
            "error": details.get(
                "error",
                "Worker request failed.",
            ),
            "stage": "worker_http",
            "worker_http_status": exc.code,
        }, exc.code

    except (URLError, TimeoutError, OSError) as exc:
        current_app.logger.warning(
            "Worker connection failed: %s",
            type(exc).__name__,
        )

        return None, {
            "error": "Could not reach the worker.",
            "stage": "connection",
        }, 502


@worker.route("/status", methods=["GET"])
@worker.route("/api/status", methods=["GET"])
@login_required
def status():
    require_admin()

    data, error, code = worker_request("/worker/status")

    if error:
        return jsonify({
            "service": "PRIME ZENITH Worker",
            "connected": False,
            **error,
        }), code

    return jsonify(data), 200


@worker.route("/pterodactyl/status", methods=["GET"])
@login_required
def pterodactyl_status():
    require_admin()

    base_url, _ = get_worker_config()

    data, error, code = worker_request("/worker/servers")

    # Temporary diagnostics. The worker key is never returned.
    if error:
        return jsonify({
            "service": "PRIME ZENITH Pterodactyl Integration",
            "connected": False,
            "worker_base_url": base_url,
            "requested_endpoint": "/worker/servers",
            "http_status": code,
            **error,
        }), code

    servers = data.get("servers", [])

    return jsonify({
        "service": "PRIME ZENITH Pterodactyl Integration",
        "connected": True,
        "execution_enabled": True,
        "worker_base_url": base_url,
        "server_count": data.get("count", len(servers)),
        "servers": servers,
        "time": datetime.now(timezone.utc).isoformat(),
    }), 200


@worker.route(
    "/pterodactyl/servers/<identifier>/status",
    methods=["GET"],
)
@login_required
def server_status(identifier):
    require_admin()

    if not valid_identifier(identifier):
        return jsonify({
            "error": "Invalid server identifier.",
        }), 400

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
        return jsonify({
            "error": "Invalid server identifier.",
        }), 400

    payload = request.get_json(silent=True) or {}
    signal = str(payload.get("signal", "")).lower()

    if signal not in {"start", "stop", "restart"}:
        return jsonify({
            "error": "Signal must be start, stop, or restart.",
        }), 400

    data, error, code = worker_request(
        f"/worker/servers/{identifier}/power",
        method="POST",
        payload={"signal": signal},
    )

    if error:
        return jsonify(error), code

    return jsonify(data), 200
