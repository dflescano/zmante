from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
from flask_login import login_required, current_user
from . import db
from .models import PC, Maintenance, Backup, Alert, ChangeLog, Config
from .utils import compute_status

bp = Blueprint("main", __name__)

@bp.app_template_filter("yn")
def yn(value):
    return "Sí" if value else "No"

def log(action, entity, entity_id, details=""):
    username = getattr(current_user, "username", "system")
    db.session.add(ChangeLog(username=username, action=action, entity=entity, entity_id=entity_id, details=details))
    db.session.commit()

@bp.route("/")
@login_required
def index():
    cfg = Config.query.get(1)
    maint_days = cfg.maintenance_days if cfg else 7
    filt = request.args.get("f", "todos")
    pcs = PC.query.order_by(PC.name.asc()).all()
    def matches(pc):
        st = compute_status(pc, maint_days)
        if filt == "todos": return True
        if filt == "ok": return "OK" in st
        if filt == "por_vencer": return "POR VENCER" in st
        if filt == "alerta": return "ALERTA" in st or "SIN MANTENIMIENTO" in st
        if filt == "sin_mantenimiento": return "SIN MANTENIMIENTO" in st
        return True
    filtered = [pc for pc in pcs if matches(pc)]
    return render_template("index.html", pcs=filtered, compute_status=lambda pc: compute_status(pc, maint_days), filt=filt)

@bp.route("/pcs")
@login_required
def pcs_list():
    q = request.args.get("q", "").strip()
    query = PC.query
    if q:
        like = f"%{q}%"
        query = query.filter((PC.name.ilike(like)) | (PC.pc_username.ilike(like)) | (PC.physical_user.ilike(like)))
    pcs = query.order_by(PC.name.asc()).all()
    return render_template("pcs.html", pcs=pcs, q=q)

@bp.route("/pcs/new", methods=["GET","POST"])
@login_required
def pc_new():
    if getattr(current_user, "role", "user") != "admin":
        flash("Solo admin puede crear PCs.", "error")
        return redirect(url_for("main.pcs_list"))
    if request.method == "POST":
        f = request.form
        name = f.get("name","").strip()
        if not name:
            flash("El nombre de la PC es obligatorio.", "error"); return redirect(url_for("main.pc_new"))
        if PC.query.filter_by(name=name).first():
            flash("Ya existe una PC con ese nombre.", "error"); return redirect(url_for("main.pc_new"))
        pc = PC(name=name,
                pc_username=f.get("pc_username","").strip(),
                physical_user=f.get("physical_user","").strip(),
                teamviewer_id=f.get("teamviewer_id","").strip(),
                anydesk_id=f.get("anydesk_id","").strip(),
                windows_licensed=True if f.get("windows_licensed")=="on" else False,
                office_licensed=True if f.get("office_licensed")=="on" else False,
                location=f.get("location","").strip(),
                notes=f.get("notes","").strip())
        db.session.add(pc); db.session.commit()
        log("create","PC", pc.id, details=f"Creada PC {pc.name}")
        flash("PC creada correctamente.", "success"); return redirect(url_for("main.pcs_list"))
    return render_template("pc_form.html", pc=None)

@bp.route("/pcs/<int:pc_id>")
@login_required
def pc_detail(pc_id):
    pc = PC.query.get_or_404(pc_id)
    logs = ChangeLog.query.filter_by(entity="PC", entity_id=pc.id).order_by(ChangeLog.created_at.desc()).limit(20).all()
    cfg = Config.query.get(1); maint_days = cfg.maintenance_days if cfg else 7
    return render_template("pc_detail.html", pc=pc, compute_status=lambda p: compute_status(p, maint_days), logs=logs)

@bp.route("/pcs/<int:pc_id>/edit", methods=["GET","POST"])
@login_required
def pc_edit(pc_id):
    pc = PC.query.get_or_404(pc_id)
    if getattr(current_user, "role", "user") != "admin":
        flash("Solo admin puede editar.", "error")
        return redirect(url_for("main.pc_detail", pc_id=pc.id))
    if request.method == "POST":
        f = request.form
        old = (pc.name, pc.pc_username, pc.physical_user, pc.teamviewer_id, pc.anydesk_id, pc.windows_licensed, pc.office_licensed, pc.location, pc.notes)
        pc.name = f.get("name","").strip() or pc.name
        pc.pc_username = f.get("pc_username","").strip()
        pc.physical_user = f.get("physical_user","").strip()
        pc.teamviewer_id = f.get("teamviewer_id","").strip()
        pc.anydesk_id = f.get("anydesk_id","").strip()
        pc.windows_licensed = True if f.get("windows_licensed")=="on" else False
        pc.office_licensed = True if f.get("office_licensed")=="on" else False
        pc.location = f.get("location","").strip()
        pc.notes = f.get("notes","").strip()
        db.session.commit()
        log("update","PC", pc.id, details=f"Antes {old} / Después {(pc.name, pc.pc_username, pc.physical_user, pc.teamviewer_id, pc.anydesk_id, pc.windows_licensed, pc.office_licensed, pc.location, pc.notes)}")
        flash("PC actualizada.", "success")
        return redirect(url_for("main.pc_detail", pc_id=pc.id))
    return render_template("pc_form.html", pc=pc)

@bp.route("/pcs/<int:pc_id>/delete", methods=["POST"])
@login_required
def pc_delete(pc_id):
    if getattr(current_user, "role", "user") != "admin":
        flash("Solo admin puede eliminar.", "error")
        return redirect(url_for("main.pc_detail", pc_id=pc_id))
    pc = PC.query.get_or_404(pc_id)
    name = pc.name
    db.session.delete(pc); db.session.commit()
    log("delete","PC", pc_id, details=f"Eliminada PC {name}")
    flash("PC eliminada.", "success"); return redirect(url_for("main.pcs_list"))

@bp.route("/pcs/<int:pc_id>/maintenance/new", methods=["POST"])
@login_required
def maintenance_new(pc_id):
    pc = PC.query.get_or_404(pc_id)
    description = request.form.get("description","").strip()
    performed_by = request.form.get("performed_by","").strip()
    m = Maintenance(pc_id=pc.id, description=description, performed_by=performed_by, date_performed=datetime.now())
    db.session.add(m); db.session.commit()
    log("add_maintenance","Maintenance", m.id, details=f"PC {pc.name} por {performed_by}: {description}")
    open_alert = Alert.query.filter_by(pc_id=pc.id, resolved=False, kind="maintenance").first()
    if open_alert:
        open_alert.resolved = True; open_alert.resolved_at = datetime.now(); db.session.commit()
        log("resolve_alert","Alert", open_alert.id, details=f"Resuelta por mantenimiento en {pc.name}")
    flash("Mantenimiento registrado.", "success")
    return redirect(url_for("main.pc_detail", pc_id=pc.id))

@bp.route("/pcs/<int:pc_id>/backup/new", methods=["POST"])
@login_required
def backup_new(pc_id):
    pc = PC.query.get_or_404(pc_id)
    status = request.form.get("status","OK").strip() or "OK"
    size_mb = request.form.get("size_mb","").strip()
    try: size_val = float(size_mb) if size_mb else None
    except ValueError: size_val = None
    path = request.form.get("path","").strip()
    b = Backup(pc_id=pc.id, status=status, size_mb=size_val, path=path, date_performed=datetime.now())
    db.session.add(b); db.session.commit()
    log("add_backup","Backup", b.id, details=f"PC {pc.name}: status={status}, size={size_val}, path={path}")
    # Cierra alerta de backup si había
    open_alert_b = Alert.query.filter_by(pc_id=pc.id, resolved=False, kind="backup").first()
    if open_alert_b:
        open_alert_b.resolved = True; open_alert_b.resolved_at = datetime.now(); db.session.commit()
        log("resolve_alert","Alert", open_alert_b.id, details=f"Resuelta por backup en {pc.name}")
    flash("Backup registrado.", "success")
    return redirect(url_for("main.pc_detail", pc_id=pc.id))

# Admin-only edit/delete for maintenance/backup
@bp.route("/maintenance/<int:m_id>/edit", methods=["GET","POST"])
@login_required
def maintenance_edit(m_id):
    m = Maintenance.query.get_or_404(m_id)
    pc = PC.query.get_or_404(m.pc_id)
    if getattr(current_user, "role", "user") != "admin":
        flash("Solo admin puede editar mantenimientos.", "error")
        return redirect(url_for("main.pc_detail", pc_id=pc.id))
    if request.method == "POST":
        old = (m.date_performed, m.performed_by, m.description)
        m.performed_by = request.form.get("performed_by","").strip()
        m.description = request.form.get("description","").strip()
        db.session.commit()
        log("update","Maintenance", m.id, details=f"Antes {old} / Después {(m.date_performed, m.performed_by, m.description)}")
        flash("Mantenimiento actualizado.", "success")
        return redirect(url_for("main.pc_detail", pc_id=pc.id))
    return render_template("maintenance_form.html", pc=pc, m=m)

@bp.route("/maintenance/<int:m_id>/delete", methods=["POST"])
@login_required
def maintenance_delete(m_id):
    m = Maintenance.query.get_or_404(m_id)
    pc = PC.query.get_or_404(m.pc_id)
    if getattr(current_user, "role", "user") != "admin":
        flash("Solo admin puede borrar mantenimientos.", "error")
        return redirect(url_for("main.pc_detail", pc_id=pc.id))
    mid = m.id
    db.session.delete(m); db.session.commit()
    log("delete","Maintenance", mid, details=f"Borrado mantenimiento de PC {pc.name}")
    flash("Mantenimiento eliminado.", "success")
    return redirect(url_for("main.pc_detail", pc_id=pc.id))

@bp.route("/backup/<int:b_id>/edit", methods=["GET","POST"])
@login_required
def backup_edit(b_id):
    b = Backup.query.get_or_404(b_id)
    pc = PC.query.get_or_404(b.pc_id)
    if getattr(current_user, "role", "user") != "admin":
        flash("Solo admin puede editar backups.", "error")
        return redirect(url_for("main.pc_detail", pc_id=pc.id))
    if request.method == "POST":
        old = (b.date_performed, b.status, b.size_mb, b.path)
        status = request.form.get("status","OK").strip() or "OK"
        size_mb = request.form.get("size_mb","").strip()
        try: size_val = float(size_mb) if size_mb else None
        except ValueError: size_val = None
        path = request.form.get("path","").strip()
        b.status = status; b.size_mb = size_val; b.path = path
        db.session.commit()
        log("update","Backup", b.id, details=f"Antes {old} / Después {(b.date_performed, b.status, b.size_mb, b.path)}")
        flash("Backup actualizado.", "success")
        return redirect(url_for("main.pc_detail", pc_id=pc.id))
    return render_template("backup_form.html", pc=pc, b=b)

@bp.route("/backup/<int:b_id>/delete", methods=["POST"])
@login_required
def backup_delete(b_id):
    b = Backup.query.get_or_404(b_id)
    pc = PC.query.get_or_404(b.pc_id)
    if getattr(current_user, "role", "user") != "admin":
        flash("Solo admin puede borrar backups.", "error")
        return redirect(url_for("main.pc_detail", pc_id=pc.id))
    bid = b.id
    db.session.delete(b); db.session.commit()
    log("delete","Backup", bid, details=f"Borrado backup de PC {pc.name}")
    flash("Backup eliminado.", "success")
    return redirect(url_for("main.pc_detail", pc_id=pc.id))

@bp.route("/alerts")
@login_required
def alerts_list():
    alerts = Alert.query.order_by(Alert.created_at.desc()).all()
    return render_template("alerts.html", alerts=alerts)

@bp.route("/alerts/<int:alert_id>/resolve", methods=["POST"])
@login_required
def alerts_resolve(alert_id):
    a = Alert.query.get_or_404(alert_id)
    if not a.resolved:
        a.resolved = True
        a.resolved_at = datetime.now()
        db.session.commit()
        flash("Alerta resuelta.", "success")
    return redirect(url_for("main.alerts_list"))
