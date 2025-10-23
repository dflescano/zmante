
import os
from pathlib import Path
from typing import List, Optional
from flask import Blueprint, render_template, current_app, send_from_directory, abort, flash, redirect, url_for, request
from flask_login import login_required, current_user
from .models import Task
from . import db

bp = Blueprint("tasksx", __name__, template_folder="templates", url_prefix="/tasks")

def _base_upload_tasks_dir() -> Path:
    base = current_app.config.get("UPLOAD_FOLDER") or os.path.join(current_app.root_path, "uploads")
    return Path(base) / "tasks"

def _unsafe_path(filename: str) -> bool:
    # Evita traversal y rutas absolutas Windows/Linux
    if not filename:
        return True
    if ".." in filename:
        return True
    # ✅ Opción robusta:
    import os
    if os.path.isabs(filename):   # C:\..., D:\..., /home/..., etc.
        return True
    # ✅ Si preferís mantener startswith, usá doble backslash:
    # if filename.startswith(("/", "\\")):
    #     return True
    if ":" in filename:           # C:\
        return True
    return False

def _attachment_records(task) -> Optional[List]:
    if task is None:
        return None
    for attr in ("attachments", "files", "uploads", "task_files", "documents"):
        if hasattr(task, attr):
            try:
                coll = getattr(task, attr)
                iter(coll)
                return list(coll)
            except Exception:
                continue
    return None

def _record_to_path(rec) -> Optional[Path]:
    cand_attrs = ("path", "filepath", "file_path", "filename", "name")
    val = None
    for a in cand_attrs:
        if hasattr(rec, a):
            val = getattr(rec, a)
            if val:
                break
    if not val:
        return None
    p = Path(val)
    if not p.is_absolute():
        if str(p).startswith("uploads") or str(p).startswith("static"):
            p = Path(current_app.root_path) / p
        else:
            p = _base_upload_tasks_dir() / p.name
    return p

def _paths_from_records(recs: List) -> List[Path]:
    out = []
    for r in recs:
        p = _record_to_path(r)
        if p and p.exists() and p.is_file():
            out.append(p)
    return out

def _resolve_file_for_task(task_id: int, filename: str) -> Optional[Path]:
    if _unsafe_path(filename):
        return None
    task = Task.query.get(task_id)
    name = os.path.basename(filename)
    recs = _attachment_records(task) if task else None
    if recs:
        for p in _paths_from_records(recs):
            if p.name == name:
                return p
    flat = _base_upload_tasks_dir() / name
    if flat.exists() and flat.is_file():
        return flat
    return None

def _list_files_for_preview(task_id: int):
    task = Task.query.get(task_id)
    recs = _attachment_records(task) if task else None
    if recs:
        paths = _paths_from_records(recs)
        base = os.path.commonpath([str(p.parent) for p in paths]) if paths else "(sin archivos)"
        return [p.name for p in paths], "db", base
    base = _base_upload_tasks_dir()
    if base.exists():
        files = [p.name for p in sorted(base.iterdir()) if p.is_file()]
        return files, "flat", str(base)
    return [], "flat", str(base)

@bp.route("/<int:task_id>/files")
@login_required
def files(task_id):
    task = Task.query.get_or_404(task_id)
    names, mode, base_shown = _list_files_for_preview(task_id)
    has_tasks_list = "main.tasks_list" in current_app.view_functions
    back_url = url_for("main.tasks_list") if has_tasks_list else url_for("main.index")
    return render_template("task_files.html", task=task, files=names, back_url=back_url, resolved_dir=base_shown, mode=mode)

@bp.route("/files/<int:task_id>/<path:filename>")
@login_required
def file_serve(task_id, filename):
    p = _resolve_file_for_task(task_id, filename)
    if not p:
        abort(404)
    return send_from_directory(p.parent.as_posix(), p.name, as_attachment=False)

@bp.route("/<int:task_id>/files/delete/<path:filename>", methods=["POST"])
@login_required
def delete_file(task_id, filename):
    if getattr(current_user, "role", "") != "admin":
        abort(403)
    p = _resolve_file_for_task(task_id, filename)
    if not p:
        flash("Archivo no encontrado.", "warning")
        return redirect(url_for("tasksx.files", task_id=task_id))
    try:
        p.unlink()
        flash("Archivo eliminado.", "success")
    except Exception as e:
        flash(f"No se pudo eliminar el archivo: {e}", "danger")
    return redirect(url_for("tasksx.files", task_id=task_id))

@bp.route("/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    if getattr(current_user, "role", "") != "admin":
        abort(403)
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash("Tarea eliminada.", "success")
    next_url = request.args.get("next") or (url_for("main.tasks_list") if "main.tasks_list" in current_app.view_functions else url_for("main.index"))
    return redirect(next_url)
