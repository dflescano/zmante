import os
from zoneinfo import ZoneInfo
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone as _pytz_tz
from datetime import datetime, timedelta

# Extensiones globales
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
scheduler = BackgroundScheduler()


def create_app():
    app = Flask(__name__)

    # --- Config básica ---
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "devkey-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///pc_maintenance.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # --- TZ / UTF-8 ---
    app.config["TZ_NAME"] = os.environ.get("TZ_NAME", "America/Argentina/Buenos_Aires")
    app.config["APP_TZ"]  = ZoneInfo(app.config["TZ_NAME"])
    app.config["NAIVE_AS"] = os.environ.get("NAIVE_AS", "UTC")  # <-- CLAVE
    app.config["JSON_AS_ASCII"] = False

    # --- Carpeta de subidas ---
    base_upload = os.path.join(app.root_path, "uploads")
    app.config["UPLOAD_FOLDER"] = os.environ.get("UPLOAD_FOLDER", base_upload)
    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "tasks"), exist_ok=True)
    app.config.setdefault("MAX_CONTENT_LENGTH", 25 * 1024 * 1024)  # 25MB

    # --- Inicializar extensiones ---
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    # --- Importar modelos (incluye Task/TaskAttachment) y blueprints ---
    from .models import (
        PC, Maintenance, Backup, Alert, User, ChangeLog, Config, EmailLog,
        Task, TaskAttachment,
    )  # noqa

    from .routes import bp as main_bp
    from .auth import bp as auth_bp
    from .exports import bp as export_bp
    from .exports_extra import bp as exportx_bp
    from .admin import bp as admin_bp
    from .tasks import bp as tasks_bp
    from .tasks_addons import bp as tasksx_bp
    from .tasks_import import bp as tasksimp_bp
    from .reports import bp as reports_bp
    from .inventory import bp as inventory_bp
    from .inventory_models import InventoryItem  # asegura creación de tabla
    from .time_helpers import to_local, now_local
    
    # --- Registrar blueprints ---
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(export_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(tasks_bp, url_prefix="/tasks")
    app.register_blueprint(tasksx_bp)  # usa url_prefix="/tasks" internamente
    app.register_blueprint(tasksimp_bp, url_prefix="/tasks")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(inventory_bp, url_prefix="/inventory")
	
	# --- Exportaciones extra: XLS y PDF (tasks/pcs) ---
    try:
        from .exports_extra import bp as exportx_bp
        # Opción A (recomendada): SIN url_prefix porque las rutas en exports_extra.py ya empiezan con /export/...
        app.register_blueprint(exportx_bp)
    
        # Debug opcional para confirmar que están los endpoints:
        print("Endpoints exportx:",
              [r.endpoint for r in app.url_map.iter_rules()
               if str(r.endpoint).startswith("exportx.")])
    except Exception as e:
        print("ERROR registrando exportx:", e)

   

    # diag_tz es opcional: no romper si falta
    try:
        from .diag_tz import bp as diag_bp
        app.register_blueprint(diag_bp, url_prefix="/diagnostico")
    except ModuleNotFoundError:
        pass

    # (debug opcional) Ver rutas de tasks
    try:
        print("Rutas tasks:", [r.rule for r in app.url_map.iter_rules() if str(r.endpoint).startswith("tasks.")])
    except Exception:
        pass

    # --- Import tardío para evitar ciclos ---
    from . import utils as _utils
    pc_created_date = _utils.pc_created_date

    # --- DB mínima: admin y config por defecto ---
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            User.create_user("admin", os.environ.get("ADMIN_PASSWORD", "admin"), role="admin")
        if not Config.query.get(1):
            cfg = Config(id=1)
            db.session.add(cfg)
            db.session.commit()

    # --- Filtro Jinja: hora local ---
    from .time_helpers import to_local

    def _fmt_local(dt, fmt="%Y-%m-%d %H:%M"):
        if not dt:
            return ""
        return to_local(dt).strftime(fmt)

    app.jinja_env.filters["localtime"] = _fmt_local


    # --- Scheduler con TZ local ---
    scheduler.configure(timezone=_pytz_tz(app.config["TZ_NAME"]))

    # --- Forzar header UTF-8 en HTML ---
    @app.after_request
    def _force_utf8(resp):
        if resp.mimetype in ("text/html", "application/xhtml+xml"):
            resp.headers["Content-Type"] = "text/html; charset=utf-8"
        return resp

    # ====================== Helpers internos ======================
    def get_config_values():
        cfg = Config.query.get(1)
        return {
            "SMTP_HOST": (cfg.smtp_host if cfg else None) or os.environ.get("SMTP_HOST"),
            "SMTP_PORT": int((cfg.smtp_port if cfg else None) or os.environ.get("SMTP_PORT", "587") or 587),
            "SMTP_TLS": (bool(cfg.smtp_tls) if cfg is not None else (os.environ.get("SMTP_TLS", "true").lower() in ("1", "true", "yes", "on"))),
            "SMTP_USER": (cfg.smtp_user if cfg else None) or os.environ.get("SMTP_USER"),
            "SMTP_PASS": (cfg.smtp_pass if cfg else None) or os.environ.get("SMTP_PASS"),
            "MAIL_FROM": (cfg.mail_from if cfg else None) or os.environ.get("MAIL_FROM"),
            "MAIL_TO": (cfg.mail_to if cfg else None) or os.environ.get("MAIL_TO"),
            "MAINT_DAYS": int((cfg.maintenance_days if cfg else None) or 7),
            "BACKUP_DAYS": int((cfg.backup_days if cfg else None) or 7),
            "ALERTS_ENABLED": (bool(cfg.alerts_enabled) if cfg is not None else True),
            "SUMMARY_DAILY": (bool(cfg.summary_daily) if cfg is not None else False),
            "SUMMARY_HOUR": int(os.environ.get("SUMMARY_HOUR", "9")),
            "SUMMARY_MINUTE": int(os.environ.get("SUMMARY_MINUTE", "0")),
        }

    def _send_email(subject, body, to_override=None):
        """Envío centralizado con logging robusto en EmailLog.
        Loguea SIEMPRE, aunque SMTP falle o la config esté incompleta.
        """
        import smtplib
        from email.message import EmailMessage
        from sqlalchemy.exc import SQLAlchemyError

        vals = get_config_values()
        host = vals.get("SMTP_HOST")
        port = vals.get("SMTP_PORT", 587)
        use_tls = vals.get("SMTP_TLS", True)
        user = vals.get("SMTP_USER")
        pwd = vals.get("SMTP_PASS")
        mail_from = vals.get("MAIL_FROM")
        mail_to = to_override or vals.get("MAIL_TO")

        ok = False
        info, err = "", None

        try:
            if not host:
                raise Exception("SMTP_HOST no configurado.")
            if not mail_from:
                raise Exception("MAIL_FROM no configurado.")
            if not mail_to:
                raise Exception("MAIL_TO no configurado.")

            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = mail_from
            msg["To"] = mail_to
            msg.set_content(body)

            with smtplib.SMTP(host, port, timeout=25) as s:
                code, banner = s.noop()
                info += f"Conectado: {code} {banner}\n"
                if use_tls:
                    s.starttls()
                    info += "TLS iniciado.\n"
                if user and pwd:
                    s.login(user, pwd)
                    info += "Login OK.\n"
                s.send_message(msg)
                info += "Mensaje enviado.\n"
            ok = True
        except Exception as e:
            err = str(e)

        # Log SIEMPRE (aunque haya fallado arriba)
        try:
            log = EmailLog(subject=subject, recipients=str(mail_to), ok=ok, info=info, error=err)
            db.session.add(log)
            db.session.commit()
        except Exception as dberr:
            db.session.rollback()
            print("[EmailLog] Error guardando log:", dberr, "| Datos:", subject, mail_to, ok, info, err)

        return ok

    # Exponer envío para otros módulos/blueprints
    app._send_email = _send_email

    def send_alert_email(pc_name, days, kind="maintenance"):
        subj = f"[Alerta {kind}] {pc_name} supera {days} días sin {'mantenimiento' if kind=='maintenance' else 'backup'}"
        body = f"La PC '{pc_name}' superó {days} días sin {'mantenimiento' if kind=='maintenance' else 'backup'}."
        app._send_email(subj, body)

    # ====================== Jobs (scheduler) ======================
    def check_maintenance_job():
        print("[scheduler] run check_maintenance_job", datetime.now())
        from .models import PC, Alert
        with app.app_context():
            vals = get_config_values()
            alerts_enabled_flag = vals.get("ALERTS_ENABLED", True)
            maint_days = vals.get("MAINT_DAYS", 7)
            backup_days = vals.get("BACKUP_DAYS", 7)
            now = now_local()

            for pc in PC.query.all():
                # --- Maintenance ---
                last_m = pc.last_maintenance_date()
                start_m = last_m or pc_created_date(pc)
                need_m_alert = (now.date() - start_m) >= timedelta(days=maint_days)
                if need_m_alert:
                    existing = Alert.query.filter_by(pc_id=pc.id, resolved=False, kind="maintenance").first()
                    if existing is None:
                        a = Alert(
                            pc_id=pc.id,
                            kind="maintenance",
                            message=f"Más de {maint_days} días sin mantenimiento (desde {start_m})."
                        )
                        db.session.add(a)
                        db.session.commit()
                        days = (now.date() - start_m).days
                        if alerts_enabled_flag:
                            send_alert_email(pc.name, days, kind="maintenance")
                else:
                    open_alert = Alert.query.filter_by(pc_id=pc.id, resolved=False, kind="maintenance").first()
                    if open_alert:
                        open_alert.resolved = True
                        open_alert.resolved_at = now

                # --- Backup ---
                last_b_obj = pc.last_backup()
                last_b = last_b_obj.date_performed.date() if last_b_obj else None
                start_b = last_b or pc_created_date(pc)
                need_b_alert = (now.date() - start_b) >= timedelta(days=backup_days)
                if need_b_alert:
                    existing_b = Alert.query.filter_by(pc_id=pc.id, resolved=False, kind="backup").first()
                    if existing_b is None:
                        a2 = Alert(
                            pc_id=pc.id,
                            kind="backup",
                            message=f"Más de {backup_days} días sin backup (desde {start_b})."
                        )
                        db.session.add(a2)
                        db.session.commit()
                        daysb = (now.date() - start_b).days
                        if alerts_enabled_flag:
                            send_alert_email(pc.name, daysb, kind="backup")
                else:
                    open_alert_b = Alert.query.filter_by(pc_id=pc.id, resolved=False, kind="backup").first()
                    if open_alert_b:
                        open_alert_b.resolved = True
                        open_alert_b.resolved_at = now

            db.session.commit()

    def send_daily_summary():
        print("[scheduler] run send_daily_summary", datetime.now())
        from .models import PC
        with app.app_context():
            vals = get_config_values()
            if not (vals.get("ALERTS_ENABLED", True) and vals.get("SUMMARY_DAILY", False)):
                return
            maint_days = vals.get("MAINT_DAYS", 7)
            backup_days = vals.get("BACKUP_DAYS", 7)
            today = now_local().date()

            def age_or_start(last_date, pc):
                start = last_date or pc_created_date(pc)
                return (today - start).days

            pcs = PC.query.order_by(PC.name.asc()).all()
            lines = ["Resumen diario de PCs en alerta:", ""]
            count = 0
            for pc in pcs:
                lm = pc.last_maintenance_date()
                lb_obj = pc.last_backup()
                lb = lb_obj.date_performed.date() if lb_obj else None
                days_m = age_or_start(lm, pc)
                days_b = age_or_start(lb, pc)
                if days_m >= maint_days or days_b >= backup_days:
                    count += 1
                    lines.append(f"- {pc.name}: mant={days_m} días, backup={days_b} días")
            if count == 0:
                lines.append("Sin alertas.")
            app._send_email("[Resumen diario] Estado de PCs", "\n".join(lines))

    # ====================== Scheduler (start) ======================
    should_start = (not app.debug) or (os.environ.get("WERKZEUG_RUN_MAIN") in ("true", "True", "1"))
    if not scheduler.running and should_start:
        interval_min = int(os.environ.get("CHECK_INTERVAL_MINUTES", "1"))
        scheduler.add_job(
            check_maintenance_job, "interval",
            minutes=interval_min, id="check_maintenance", replace_existing=True
        )
        vals_env_hour = int(os.environ.get("SUMMARY_HOUR", "9"))
        vals_env_min = int(os.environ.get("SUMMARY_MINUTE", "0"))
        scheduler.add_job(
            send_daily_summary, "cron",
            hour=vals_env_hour, minute=vals_env_min, id="daily_summary", replace_existing=True
        )
        scheduler.start()
        print("[scheduler] iniciado (debug=%s, main=%s, interval=%s min)" %
              (app.debug, os.environ.get("WERKZEUG_RUN_MAIN"), interval_min))

    # Exponer jobs para Admin
    app.check_maintenance_job = check_maintenance_job
    app.send_daily_summary = send_daily_summary

    return app
