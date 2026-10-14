import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Blueprint, jsonify, abort
from flask_login import login_required, current_user

worker = Blueprint("worker", __name__, url_prefix="/worker")


def is_admin():
    return bool(getattr(current_user, "is_admin", False))


def pterodactyl_request(endpoint):
    base_url = os.environ.get("PTERODACTYL_URL", "").strip().rstrip("/")
    api_key = os.environ.get("PTERODACTYL_API_KEY", "").strip()

    if not base_url or not api_key:
        return None, {
            "error": "Pterodactyl environment variables are missing."
        }, 503

    if not base_url.startswith("https://"):
        return None, {
            "error": "PTERODACTYL_URL must use HTTPS."
        }, 503

    url = base_url + endpoint
    req = Request(
        url,
        headers={
            "Authorization": "Bearer " + api_key,
            "Accept": "application/vnd.pterodactyl.v1+json",
            "Content-Type": "application/json",
            "User-Agent": "PRIME-ZENITH-Panel/1.0",
        },
        method="GET",
    )

    try:
        with urlopen(req, timeout=15) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
            try:
                data = json.loads(body.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return None, {
                    "error": "Pterodactyl returned non-JSON data.",
                    "http_status": response.status,
                    "content_type": content_type,
                    "response_preview": body[:160].decode("utf-8", "replace"),
                }, 502
            return data, None, response.status

    except HTTPError as exc:
        if exc.code == 401:
            message = "API key is invalid or unauthorized."
        elif exc.code == 403:
            message = "API key lacks permission for this endpoint."
        elif exc.code == 404:
            message = "Pterodactyl API endpoint was not found."
        else:
            message = "Pterodactyl returned HTTP " + str(exc.code)

        return None, {"error": message}, exc.code

    except (URLError, TimeoutError, OSError) as exc:
        return None, {
            "error": "Could not reach the Pterodactyl panel.",
            "detail": str(exc)[:200],
        }, 502

    except Exception as exc:
        return None, {
            "error": "Pterodactyl request failed unexpectedly.",
            "detail": type(exc).__name__ + ": " + str(exc)[:200],
        }, 502


@worker.route("/status", methods=["GET"])
@worker.route("/api/status", methods=["GET"])
@login_required
def status():
    if not is_admin():
        abort(403)

    configured = bool(
        os.environ.get("PTERODACTYL_URL", "").strip()
        and os.environ.get("PTERODACTYL_API_KEY", "").strip()
    )

    return jsonify(
        service="PRIME ZENITH Pterodactyl Integration",
        connected=False,
        integration_configured=configured,
        execution_enabled=False,
        message=(
            "Configuration found. Use /worker/pterodactyl/status "
            "to test the actual API connection."
            if configured else
            "Set PTERODACTYL_URL and PTERODACTYL_API_KEY in Render."
        ),
        time=datetime.now(timezone.utc).isoformat(),
    ), 200


@worker.route("/pterodactyl/status", methods=["GET"])
@login_required
def pterodactyl_status():
    if not is_admin():
        abort(403)

    data, error, status_code = pterodactyl_request("/api/client/servers")

    if error:
        return jsonify(
            service="PRIME ZENITH Pterodactyl Integration",
            connected=False,
            execution_enabled=False,
            **error,
        ), status_code

    servers = []
    for item in data.get("data", []):
        attributes = item.get("attributes", {})
        servers.append({
            "name": attributes.get("name", "Unnamed server"),
            "identifier": attributes.get("identifier"),
            "uuid": attributes.get("uuid"),
            "suspended": attributes.get("is_suspended", False),
            "limits": attributes.get("limits", {}),
        })

    return jsonify(
        service="PRIME ZENITH Pterodactyl Integration",
        connected=True,
        execution_enabled=False,
        server_count=len(servers),
        servers=servers,
        message="Pterodactyl Client API connection successful.",
        time=datetime.now(timezone.utc).isoformat(),
    ), 200
