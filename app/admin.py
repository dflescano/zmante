from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from .models import Alert, User, Config, EmailLog
from . import db

bp = Blueprint("admin", __name__, template_folder="templates")

def require_admin():
    return getattr(current_user, "role", "user") == "admin"

@bp.route("/users")
@login_required
def users_list():
    if not require_admin():
        flash("Solo admin puede ver usuarios.", "error")
        return redirect(url_for("main.index"))
    users = User.query.order_by(User.username.asc()).all()
    return render_template("users.html", users=users)

@bp.route("/users/new", methods=["GET","POST"])
@login_required
def users_new():
    if not require_admin():
        flash("Solo admin puede crear usuarios.", "error")
        return redirect(url_for("admin.users_list"))
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","").strip()
        role = request.form.get("role","user")
        if not username or not password:
            flash("Usuario y contraseña son obligatorios.", "error"); return redirect(url_for("admin.users_new"))
        if User.query.filter_by(username=username).first():
            flash("Ya existe un usuario con ese nombre.", "error"); return redirect(url_for("admin.users_new"))
        User.create_user(username, password, role=role)
        flash("Usuario creado.", "success")
        return redirect(url_for("admin.users_list"))
    return render_template("user_form.html", user=None)

@bp.route("/users/<int:uid>/edit", methods=["GET","POST"])
@login_required
def users_edit(uid):
    if not require_admin():
        flash("Solo admin puede editar usuarios.", "error")
        return redirect(url_for("admin.users_list"))
    u = User.query.get_or_404(uid)
    if request.method == "POST":
        role = request.form.get("role","user")
        newpass = request.form.get("password","").strip()
        u.role = role
        if newpass:
            u.password_hash = generate_password_hash(newpass)
        db.session.commit()
        flash("Usuario actualizado.", "success")
        return redirect(url_for("admin.users_list"))
    return render_template("user_form.html", user=u)

@bp.route("/users/<int:uid>/delete", methods=["POST"])
@login_required
def users_delete(uid):
    if not require_admin():
        flash("Solo admin puede borrar usuarios.", "error")
        return redirect(url_for("admin.users_list"))
    u = User.query.get_or_404(uid)
    if u.username == "admin":
        flash("No se puede borrar el usuario admin por defecto.", "error")
        return redirect(url_for("admin.users_list"))
    db.session.delete(u); db.session.commit()
    flash("Usuario eliminado.", "success")
    return redirect(url_for("admin.users_list"))

@bp.route("/mail-test", methods=["GET","POST"])
@login_required
def mail_test():
    if not require_admin():
        flash("Solo admin puede probar correo.", "error")
        return redirect(url_for("main.index"))
    import os, smtplib
    from email.message import EmailMessage
    defaults = {
        "SMTP_HOST": os.environ.get("SMTP_HOST",""),
        "SMTP_PORT": os.environ.get("SMTP_PORT","587"),
        "SMTP_TLS": os.environ.get("SMTP_TLS","true"),
        "SMTP_USER": os.environ.get("SMTP_USER",""),
        "SMTP_PASS": os.environ.get("SMTP_PASS",""),
        "MAIL_FROM": os.environ.get("MAIL_FROM",""),
        "MAIL_TO": os.environ.get("MAIL_TO",""),
        "SUBJECT": "Prueba de alertas - Sistema Mantenimiento",
        "BODY": "Este es un correo de prueba del sistema de mantenimiento."
    }
    if request.method == "POST":
        host = request.form.get("SMTP_HOST") or defaults["SMTP_HOST"]
        port = int(request.form.get("SMTP_PORT") or defaults["SMTP_PORT"] or 587)
        use_tls = (request.form.get("SMTP_TLS") or defaults["SMTP_TLS"] or "true").lower() in ("1","true","yes","on")
        user = request.form.get("SMTP_USER") or defaults["SMTP_USER"]
        pwd  = request.form.get("SMTP_PASS") or defaults["SMTP_PASS"]
        mail_from = request.form.get("MAIL_FROM") or defaults["MAIL_FROM"]
        mail_to   = request.form.get("MAIL_TO") or defaults["MAIL_TO"]
        subject   = request.form.get("SUBJECT") or defaults["SUBJECT"]
        body      = request.form.get("BODY") or defaults["BODY"]
        try:
            if not (host and mail_from and mail_to):
                raise Exception("Faltan SMTP_HOST, MAIL_FROM, MAIL_TO.")
            msg = EmailMessage()
            msg["Subject"] = subject; msg["From"] = mail_from; msg["To"] = mail_to
            msg.set_content(body)
            info = ""
            with smtplib.SMTP(host, port, timeout=25) as s:
                code, banner = s.noop(); info += f"Conectado: {code} {banner}\n"
                if use_tls: s.starttls(); info += "TLS iniciado.\n"
                if user and pwd: s.login(user, pwd); info += "Login OK.\n"
                s.send_message(msg); info += "Mensaje enviado.\n"
            flash("Correo de prueba enviado correctamente.", "success"); flash(info, "success")
        except Exception as e:
            flash("Error enviando correo de prueba.", "error"); flash(str(e), "error")
    return render_template("mail_test.html", defaults=defaults)

@bp.route("/settings", methods=["GET","POST"])
@login_required
def settings():
    if not require_admin():
        flash("Solo admin puede cambiar la configuración.", "error")
        return redirect(url_for("main.index"))
    cfg = Config.query.get(1)
    if request.method == "POST":
        if not cfg:
            cfg = Config(id=1); db.session.add(cfg)
        f = request.form
        cfg.smtp_host = f.get("smtp_host") or None
        try: cfg.smtp_port = int(f.get("smtp_port") or 587)
        except: cfg.smtp_port = 587
        cfg.smtp_tls = True if f.get("smtp_tls") == "on" else False
        cfg.smtp_user = f.get("smtp_user") or None
        cfg.smtp_pass = f.get("smtp_pass") or None
        cfg.mail_from = f.get("mail_from") or None
        cfg.mail_to = f.get("mail_to") or None
        try: cfg.maintenance_days = int(f.get("maintenance_days") or 7)
        except: cfg.maintenance_days = 7
        try: cfg.backup_days = int(f.get("backup_days") or 7)
        except: cfg.backup_days = 7
        cfg.alerts_enabled = True if f.get("alerts_enabled") == "on" else False
        cfg.summary_daily = True if f.get("summary_daily") == "on" else False
        db.session.commit()
        flash("Configuración guardada.", "success")
        return redirect(url_for("admin.settings"))
    return render_template("settings.html", cfg=cfg)

@bp.route("/email-logs")
@login_required
def email_logs():
    if not require_admin():
        flash("Solo admin puede ver logs de correo.", "error")
        return redirect(url_for("main.index"))
    logs = EmailLog.query.order_by(EmailLog.created_at.desc()).limit(500).all()
    return render_template("email_logs.html", logs=logs)

@bp.route("/email-logs/clear", methods=["POST"])
@login_required
def email_logs_clear():
    if getattr(current_user, "role", "") != "admin":
        abort(403)
    EmailLog.query.delete()         # borra todas las filas
    db.session.commit()
    flash("Logs de correo eliminados.", "success")
    return redirect(url_for("admin.email_logs"))
    
    

@bp.route("/run-checks", methods=["POST"])
@login_required
def run_checks_now():
    if not require_admin():
        flash("Solo admin.", "error"); return redirect(url_for("admin.settings"))
    # Ejecuta el job inmediatamente
    from flask import current_app
    try:
        current_app.check_maintenance_job()
        flash("Recalculadas las alertas.", "success")
    except Exception as e:
        flash(f"Error al recalcular: {e}", "error")
    return redirect(url_for("admin.settings"))

@bp.route("/send-summary-now", methods=["POST"])
@login_required
def send_summary_now():
    if not require_admin():
        flash("Solo admin.", "error"); return redirect(url_for("admin.settings"))
    from flask import current_app
    try:
        # Forzar envío de resumen aunque ALERTS_ENABLED esté apagado: llamamos al privado de envío
        current_app.send_daily_summary()
        flash("Resumen enviado (si SUMMARY_DAILY está activo y hay config SMTP).", "success")
    except Exception as e:
        flash(f"Error al enviar resumen: {e}", "error")
    return redirect(url_for("admin.settings"))

@bp.route("/diagnostics")
@login_required
def diagnostics():
    if not require_admin():
        flash("Solo admin.", "error"); return redirect(url_for("main.index"))
    from datetime import datetime, timedelta
    from .models import PC, Config
    from . import db
    cfg = Config.query.get(1)
    today = datetime.now().date()
    maint_days = cfg.maintenance_days if cfg else 7
    backup_days = cfg.backup_days if cfg else 7
    rows = []
    def age(d):
        if d is None: return None
        return (today - d).days
    for pc in PC.query.order_by(PC.name.asc()).all():
        lm = pc.last_maintenance_date()
        lb = pc.last_backup().date_performed.date() if pc.last_backup() else None
        rows.append({
            "pc": pc.name,
            "last_maint": str(lm) if lm else "None",
            "last_backup": str(lb) if lb else "None",
            "age_maint": age(lm),
            "age_backup": age(lb),
            "should_alert_maint": (lm is None) or (age(lm) is not None and age(lm) > maint_days),
            "should_alert_backup": (lb is None) or (age(lb) is not None and age(lb) > backup_days),
        })
    return render_template("diagnostics.html", cfg=cfg, rows=rows)

@bp.route("/alerts/<int:alert_id>/delete", methods=["POST"])
@login_required
def alerts_delete(alert_id):
    # Solo admin puede borrar alertas
    if getattr(current_user, "role", "") != "admin":
        abort(403)
    a = Alert.query.get_or_404(alert_id)
    db.session.delete(a)
    db.session.commit()
    flash("Alerta eliminada.", "success")
    return redirect(url_for("main.alerts_list"))