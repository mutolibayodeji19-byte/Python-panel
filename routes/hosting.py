import os
import posixpath
import shutil
import zipfile
from pathlib import Path

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, abort, current_app
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from database.database import db
from database.hosting_models import HostingServer

hosting = Blueprint("hosting", __name__, url_prefix="/hosting")
ALLOWED_RUNTIMES = {"python", "node"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_ZIP_FILES = 200
MAX_ZIP_UNPACKED = 50 * 1024 * 1024


def server_dir(server):
    root = Path(current_app.instance_path) / "hosting_data"
    root.mkdir(parents=True, exist_ok=True)
    folder = root / str(server.id)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def get_server(server_id):
    server = db.session.get(HostingServer, server_id)
    if server is None:
        abort(404)
    if server.owner_id != current_user.id and not getattr(current_user, "is_admin", False):
        abort(403)
    return server


def list_files(folder):
    result = []
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            result.append({
                "name": path.relative_to(folder).as_posix(),
                "size": path.stat().st_size
            })
    return result[:500]


def safe_zip_extract(archive, destination):
    with zipfile.ZipFile(archive) as zf:
        entries = [x for x in zf.infolist() if not x.is_dir()]
        if len(entries) > MAX_ZIP_FILES:
            raise ValueError("ZIP contains too many files (maximum 200).")

        total = sum(x.file_size for x in entries)
        if total > MAX_ZIP_UNPACKED:
            raise ValueError("ZIP expands beyond the 50 MB limit.")

        for item in entries:
            name = item.filename.replace("\\", "/")
            normalized = posixpath.normpath(name)

            if (name.startswith("/") or normalized in (".", "..")
                    or normalized.startswith("../")
                    or ":" in normalized.split("/")[0]):
                raise ValueError("ZIP contains an unsafe file path.")

            # Do not extract symbolic links.
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("ZIP symbolic links are not allowed.")

            parts = [secure_filename(p) for p in normalized.split("/")]
            if not parts or any(not p or p in (".", "..") for p in parts):
                raise ValueError("ZIP contains an invalid filename.")

            target = destination.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(item) as source, open(target, "wb") as output:
                shutil.copyfileobj(source, output)


@hosting.route("/")
@login_required
def index():
    if getattr(current_user, "is_admin", False):
        servers = HostingServer.query.order_by(HostingServer.created_at.desc()).all()
    else:
        servers = HostingServer.query.filter_by(owner_id=current_user.id).order_by(
            HostingServer.created_at.desc()
        ).all()
    return render_template("hosting.html", servers=servers)


@hosting.route("/create", methods=["POST"])
@login_required
def create():
    name = request.form.get("name", "").strip()
    runtime = request.form.get("runtime", "").lower().strip()

    if not name or len(name) > 80:
        flash("Enter a server name of 1–80 characters.", "error")
        return redirect(url_for("hosting.index"))

    if runtime not in ALLOWED_RUNTIMES:
        flash("Choose Python or Node.js.", "error")
        return redirect(url_for("hosting.index"))

    server = HostingServer(
        name=name,
        runtime=runtime,
        owner_id=current_user.id,
        startup_command="python main.py" if runtime == "python" else "node index.js"
    )
    db.session.add(server)
    db.session.commit()
    server_dir(server)
    flash("Project created. Upload its files to continue.", "success")
    return redirect(url_for("hosting.detail", server_id=server.id))


@hosting.route("/<int:server_id>")
@login_required
def detail(server_id):
    server = get_server(server_id)
    folder = server_dir(server)
    return render_template(
        "hosting_detail.html",
        server=server,
        files=list_files(folder)
    )


@hosting.route("/<int:server_id>/upload", methods=["POST"])
@login_required
def upload(server_id):
    server = get_server(server_id)
    if request.content_length and request.content_length > MAX_UPLOAD_BYTES:
        flash("Upload too large. Maximum request size is 25 MB.", "error")
        return redirect(url_for("hosting.detail", server_id=server.id))

    folder = server_dir(server)
    uploaded = request.files.getlist("files")
    if not uploaded or all(not f.filename for f in uploaded):
        flash("Choose a file or ZIP first.", "error")
        return redirect(url_for("hosting.detail", server_id=server.id))

    try:
        for file in uploaded:
            if not file.filename:
                continue
            original = file.filename.replace("\\", "/").split("/")[-1]
            filename = secure_filename(original)
            if not filename:
                raise ValueError("A filename is invalid.")

            if filename.lower().endswith(".zip"):
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".zip") as temp:
                    file.save(temp.name)
                    safe_zip_extract(temp.name, folder)
            else:
                file.save(folder / filename)

        flash("Upload completed.", "success")
    except (ValueError, zipfile.BadZipFile, OSError) as exc:
        flash(f"Upload failed: {exc}", "error")

    return redirect(url_for("hosting.detail", server_id=server.id))


@hosting.route("/<int:server_id>/settings", methods=["POST"])
@login_required
def settings(server_id):
    server = get_server(server_id)
    command = request.form.get("startup_command", "").strip()
    if not command or len(command) > 500:
        flash("Startup command must contain 1–500 characters.", "error")
    else:
        server.startup_command = command
        db.session.commit()
        flash("Startup command saved. It is not executed until a worker is connected.", "success")
    return redirect(url_for("hosting.detail", server_id=server.id))


@hosting.route("/<int:server_id>/delete-file", methods=["POST"])
@login_required
def delete_file(server_id):
    server = get_server(server_id)
    name = request.form.get("name", "")
    folder = server_dir(server).resolve()
    target = (folder / name).resolve()

    if target == folder or folder not in target.parents or not target.is_file():
        abort(400)

    target.unlink()
    flash("File deleted.", "success")
    return redirect(url_for("hosting.detail", server_id=server.id))


@hosting.route("/<int:server_id>/delete", methods=["POST"])
@login_required
def delete_server(server_id):
    server = get_server(server_id)
    folder = server_dir(server)
    shutil.rmtree(folder, ignore_errors=True)
    db.session.delete(server)
    db.session.commit()
    flash("Project and its uploaded files were deleted.", "success")
    return redirect(url_for("hosting.index"))
