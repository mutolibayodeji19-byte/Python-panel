import ipaddress
import socket
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from database.database import db
from database.feature_models import UptimeMonitor, WhatsAppBot


features = Blueprint("features", __name__, url_prefix="/tools")


def _public_http_url(value):
    """Accept public HTTP(S) URLs only; reject private and local destinations."""
    try:
        parsed = urlparse((value or "").strip())
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return None
        if parsed.username or parsed.password:
            return None
        if parsed.port and not 1 <= parsed.port <= 65535:
            return None

        host = parsed.hostname
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
        if not addresses:
            return None

        for item in addresses:
            ip = ipaddress.ip_address(item[4][0].split("%")[0])
            if not ip.is_global:
                return None

        return parsed.geturl()
    except (ValueError, OSError, socket.gaierror):
        return None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@features.route("/uptime", methods=["GET", "POST"])
@login_required
def uptime():
    if request.method == "POST":
        action = request.form.get("action", "")
        monitor_id = request.form.get("monitor_id", type=int)

        if action == "add":
            name = request.form.get("name", "").strip()
            url = request.form.get("url", "").strip()
            safe_url = _public_http_url(url)

            if not name or len(name) > 80 or not safe_url or len(safe_url) > 500:
                flash("Enter a name and a valid public HTTP(S) URL.", "error")
            else:
                db.session.add(UptimeMonitor(
                    user_id=current_user.id, name=name, url=safe_url
                ))
                db.session.commit()
                flash("Website added.", "success")

        elif action == "delete" and monitor_id:
            item = UptimeMonitor.query.filter_by(
                id=monitor_id, user_id=current_user.id
            ).first_or_404()
            db.session.delete(item)
            db.session.commit()
            flash("Website removed.", "success")

        elif action == "check" and monitor_id:
            item = UptimeMonitor.query.filter_by(
                id=monitor_id, user_id=current_user.id
            ).first_or_404()
            safe_url = _public_http_url(item.url)

            if not safe_url:
                item.last_status = "Blocked"
                item.last_code = None
                item.last_response_ms = None
            else:
                started = time.monotonic()
                try:
                    req = Request(
                        safe_url,
                        headers={"User-Agent": "PrimeZenith-Uptime/1.0"},
                        method="GET",
                    )
                    opener = build_opener(_NoRedirect())
                    try:
                        response = opener.open(req, timeout=8)
                        code = response.getcode()
                        response.close()
                    except HTTPError as exc:
                        code = exc.code
                    elapsed = int((time.monotonic() - started) * 1000)
                    item.last_code = code
                    item.last_response_ms = elapsed
                    item.last_status = "Up" if 200 <= code < 400 else "Down"
                except (URLError, OSError, TimeoutError, ValueError):
                    item.last_code = None
                    item.last_response_ms = int((time.monotonic() - started) * 1000)
                    item.last_status = "Down"

            item.last_checked = datetime.utcnow()
            db.session.commit()
            flash("Uptime check completed.", "success")

        return redirect(url_for("features.uptime"))

    monitors = (
        UptimeMonitor.query.filter_by(user_id=current_user.id)
        .order_by(UptimeMonitor.id.desc()).all()
    )
    return render_template("uptime.html", monitors=monitors)


@features.route("/whatsapp", methods=["GET", "POST"])
@login_required
def whatsapp():
    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "add":
            name = request.form.get("name", "").strip()
            phone = request.form.get("phone_label", "").strip()
            hosting = request.form.get("hosting_label", "").strip()

            if not name or len(name) > 80 or len(phone) > 40 or len(hosting) > 120:
                flash("Check the bot name and field lengths.", "error")
            else:
                db.session.add(WhatsAppBot(
                    user_id=current_user.id,
                    name=name,
                    phone_label=phone,
                    hosting_label=hosting,
                    connection_status="Not connected",
                ))
                db.session.commit()
                flash("Bot entry saved. No live connection was started.", "success")

        elif action == "status":
            bot_id = request.form.get("bot_id", type=int)
            status = request.form.get("status", "")
            allowed = {"Not connected", "Connecting", "Connected", "Stopped", "Error"}
            bot = WhatsAppBot.query.filter_by(
                id=bot_id, user_id=current_user.id
            ).first_or_404()

            if status in allowed:
                bot.connection_status = status
                db.session.commit()
                flash("Recorded status updated. This does not control a live bot.", "success")
            else:
                flash("Invalid status.", "error")

        elif action == "delete":
            bot_id = request.form.get("bot_id", type=int)
            bot = WhatsAppBot.query.filter_by(
                id=bot_id, user_id=current_user.id
            ).first_or_404()
            db.session.delete(bot)
            db.session.commit()
            flash("Bot entry removed.", "success")

        return redirect(url_for("features.whatsapp"))

    bots = (
        WhatsAppBot.query.filter_by(user_id=current_user.id)
        .order_by(WhatsAppBot.id.desc()).all()
    )
    return render_template("whatsapp.html", bots=bots)
