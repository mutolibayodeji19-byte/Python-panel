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
    """
    Read worker configuration from the active Flask application first,
    then fall back to environment variables.
    """
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

    if not base_url.startswith("https://") or not worker_key:
        current_app.logger.error(
            "PRIME ZENITH worker configuration is incomplete."
        )
        return None, {
            "error": "Worker configuration is incomplete."
        }, 503

    # Only permit requests to the configured worker's own endpoints.
    if not path.startswith("/worker/"):
        return None, {"error": "Invalid worker endpoint."}, 400

    body = None
    headers = {
        "Accept": "application/json",
        "X-Worker-Key": worker_key,
        "User-Agent": "PRIME-ZENITH-PANEL/2.4",
    }

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    url = base_url + path

    # Log the URL and status, never the authentication key.
    current_app.logger.info(
        "PRIME ZENITH worker request: method=%s url=%s",
        method,
        url,
    )

    req = Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(req, timeout=20) as response:
            raw = response.read()

            if not raw:
                data = {}
            else:
                data = json.loads(raw.decode("utf-8"))

            current_app.logger.info(
                "PRIME ZENITH worker response: http_status=%s",
                response.status,
            )

            return data, None, response.status

    except HTTPError as exc:
        try:
            raw_error = exc.read(2000).decode("utf-8")
            details = json.loads(raw_error)
        except (ValueError, UnicodeDecodeError, OSError):
            details = {}

        message = details.get(
            "error",
            "Worker request failed."
        )

        current_app.logger.warning(
            "PRIME ZENITH worker HTTP error: status=%s path=%s",
            exc.code,
            path,
        )

        return None, {
            "error": message,
            "worker_http_status": exc.code,
        }, exc.code

    except (URLError, TimeoutError, OSError) as exc:
        current_app.logger.error(
            "PRIME ZENITH worker connection failed: %s",
            type(exc).__name__,
        )

        return None, {
            "error": "Could not reach the worker."
        }, 502

    except (ValueError, UnicodeDecodeError):
        current_app.logger.error(
            "PRIME ZENITH worker returned invalid JSON."
        )

        return None, {
            "error": "Worker returned invalid JSON."
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

    data, error, code = worker_request("/worker/servers")

    # Temporary diagnostic: no secrets are logged.
    base_url, _ = get_worker_config()

    current_app.logger.info(
        "PRIME ZENITH WORKER DEBUG: "
        "base_url=%s http_status=%s error=%s",
        base_url,
        code,
        error,
    )

    if error:
        return jsonify({
            "service": "PRIME ZENITH Pterodactyl Integration",
            "connected": False,
            **error,
        }), code

    servers = data.get("servers", [])

    return jsonify({
        "service": "PRIME ZENITH Pterodactyl Integration",
        "connected": True,
        "execution_enabled": True,
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
