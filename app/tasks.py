import os
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from . import db
from .models import Task, TaskAttachment, PC, TASK_STATUS_CHOICES, TASK_PRIORITY_CHOICES

bp = Blueprint("tasks", __name__, template_folder="templates")

def require_admin():
    return current_user.is_authenticated and getattr(current_user, "role", "") == "admin"

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf"}
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date() if s else None
    except Exception:
        return None

def ensure_task_upload_dir():
    base = current_app.config.get("UPLOAD_FOLDER", os.path.join(current_app.root_path, "uploads"))
    task_dir = os.path.join(base, "tasks")
    os.makedirs(task_dir, exist_ok=True)
    return task_dir

# --------- LISTADO / FILTRO ---------
@bp.route("/")
@login_required
def list_tasks():
    q = Task.query.order_by(Task.created_at.desc())

    status = request.args.get("status", "").strip()
    priority = request.args.get("priority", "").strip()
    pc_id = request.args.get("pc_id", "").strip()
    text = request.args.get("q", "").strip()

    if status in TASK_STATUS_CHOICES:
        q = q.filter(Task.status == status)
    if priority in TASK_PRIORITY_CHOICES:
        q = q.filter(Task.priority == priority)
    if pc_id.isdigit():
        q = q.filter(Task.pc_id == int(pc_id))
    if text:
        like = f"%{text}%"
        q = q.filter(db.or_(Task.title.ilike(like), Task.problem.ilike(like), Task.solution.ilike(like), Task.comments.ilike(like)))

    pcs = PC.query.order_by(PC.name.asc()).all()
    return render_template("tasks_list.html", tasks=q.all(), pcs=pcs,
                           status=status, priority=priority, sel_pc=pc_id, text=text)

# --------- CREAR ---------
@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_task():
    pcs = PC.query.order_by(PC.name.asc()).all()

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        problem = (request.form.get("problem") or "").strip()
        if not title or not problem:
            flash("Título y problema son obligatorios.", "error")
            return render_template("task_form.html", task=None, pcs=pcs)

        task = Task(
            title=title,
            pc_id=int(request.form.get("pc_id")) if (request.form.get("pc_id") or "").isdigit() else None,
            status=request.form.get("status") if request.form.get("status") in TASK_STATUS_CHOICES else "pendiente",
            priority=request.form.get("priority") if request.form.get("priority") in TASK_PRIORITY_CHOICES else "media",
            start_date=parse_date(request.form.get("start_date")),
            end_date=parse_date(request.form.get("end_date")),
            problem=problem,
            solution=(request.form.get("solution") or "").strip() or None,
            comments=(request.form.get("comments") or "").strip() or None,
        )
        db.session.add(task)
        db.session.commit()

        # archivos
        task_dir = ensure_task_upload_dir()
        files = request.files.getlist("files")
        for f in files:
            if not f or not getattr(f, "filename", ""):
                continue
            if not allowed_file(f.filename):
                flash(f"Archivo no permitido: {f.filename}", "error")
                continue
            ext = f.filename.rsplit(".", 1)[1].lower()
            safe = secure_filename(f.filename)
            unique_name = f"{uuid.uuid4().hex}.{ext}"
            stored_path = os.path.join(task_dir, unique_name)
            f.save(stored_path)
            att = TaskAttachment(
                task_id=task.id,
                filename=unique_name,
                original_name=safe,
                content_type=f.mimetype,
                size=os.path.getsize(stored_path),
                uploader_id=getattr(current_user, "id", None),
            )
            db.session.add(att)
        db.session.commit()
        flash("Tarea creada.", "success")
        return redirect(url_for("tasks.view_task", task_id=task.id))

    return render_template("task_form.html", task=None, pcs=pcs)

# --------- EDITAR ---------
@bp.route("/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    pcs = PC.query.order_by(PC.name.asc()).all()

    if request.method == "POST":
        task.title = (request.form.get("title") or "").strip() or task.title
        task.pc_id = int(request.form.get("pc_id")) if (request.form.get("pc_id") or "").isdigit() else None
        st = request.form.get("status")
        pr = request.form.get("priority")
        if st in TASK_STATUS_CHOICES: task.status = st
        if pr in TASK_PRIORITY_CHOICES: task.priority = pr
        task.start_date = parse_date(request.form.get("start_date"))
        task.end_date = parse_date(request.form.get("end_date"))
        task.problem = (request.form.get("problem") or "").strip() or task.problem
        task.solution = (request.form.get("solution") or "").strip() or None
        task.comments = (request.form.get("comments") or "").strip() or None
        db.session.commit()

        # nuevos archivos
        task_dir = ensure_task_upload_dir()
        files = request.files.getlist("files")
        for f in files:
            if not f or not getattr(f, "filename", ""):
                continue
            if not allowed_file(f.filename):
                flash(f"Archivo no permitido: {f.filename}", "error")
                continue
            ext = f.filename.rsplit(".", 1)[1].lower()
            safe = secure_filename(f.filename)
            unique_name = f"{uuid.uuid4().hex}.{ext}"
            stored_path = os.path.join(task_dir, unique_name)
            f.save(stored_path)
            att = TaskAttachment(
                task_id=task.id,
                filename=unique_name,
                original_name=safe,
                content_type=f.mimetype,
                size=os.path.getsize(stored_path),
                uploader_id=getattr(current_user, "id", None),
            )
            db.session.add(att)
        db.session.commit()
        flash("Tarea actualizada.", "success")
        return redirect(url_for("tasks.view_task", task_id=task.id))

    return render_template("task_form.html", task=task, pcs=pcs)

# --------- VER DETALLE ---------
@bp.route("/<int:task_id>")
@login_required
def view_task(task_id):
    task = Task.query.get_or_404(task_id)
    return render_template("task_detail.html", task=task)

# --------- BORRAR TAREA (solo admin) ---------
@bp.route("/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    if not require_admin():
        flash("Solo el administrador puede borrar tareas.", "error")
        return redirect(url_for("tasks.view_task", task_id=task_id))

    task = Task.query.get_or_404(task_id)
    # borrar archivos físicos
    task_dir = ensure_task_upload_dir()
    for att in task.attachments.all():
        try:
            os.remove(os.path.join(task_dir, att.filename))
        except Exception:
            pass
    db.session.delete(task)
    db.session.commit()
    flash("Tarea eliminada.", "success")
    return redirect(url_for("tasks.list_tasks"))

# --------- DESCARGAR ADJUNTO ---------
@bp.route("/attachment/<int:att_id>")
@login_required
def download_attachment(att_id):
    att = TaskAttachment.query.get_or_404(att_id)
    task_dir = ensure_task_upload_dir()
    path = os.path.join(task_dir, att.filename)
    if not os.path.isfile(path):
        abort(404)
    return send_from_directory(task_dir, att.filename, as_attachment=True, download_name=att.original_name or att.filename)

# --------- BORRAR ADJUNTO (admin) ---------
@bp.route("/attachment/<int:att_id>/delete", methods=["POST"])
@login_required
def delete_attachment(att_id):
    if not require_admin():
        flash("Solo el administrador puede borrar adjuntos.", "error")
        return redirect(url_for("tasks.list_tasks"))
    att = TaskAttachment.query.get_or_404(att_id)
    task_id = att.task_id
    task_dir = ensure_task_upload_dir()
    try:
        os.remove(os.path.join(task_dir, att.filename))
    except Exception:
        pass
    db.session.delete(att)
    db.session.commit()
    flash("Adjunto eliminado.", "success")
    return redirect(url_for("tasks.view_task", task_id=task_id))
