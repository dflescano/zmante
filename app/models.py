from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db, login_manager



class PC(db.Model):
    __tablename__ = "pcs"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    pc_username = db.Column(db.String(120))
    physical_user = db.Column(db.String(120))
    teamviewer_id = db.Column(db.String(120))
    anydesk_id = db.Column(db.String(120))
    windows_licensed = db.Column(db.Boolean, default=False)
    office_licensed = db.Column(db.Boolean, default=False)
    location = db.Column(db.String(120))
    notes = db.Column(db.Text)

    maintenances = db.relationship("Maintenance", backref="pc", cascade="all, delete-orphan", lazy=True)
    backups = db.relationship("Backup", backref="pc", cascade="all, delete-orphan", lazy=True)
    alerts = db.relationship("Alert", backref="pc", cascade="all, delete-orphan", lazy=True)

    def last_maintenance(self):
        return (sorted(self.maintenances, key=lambda m: m.date_performed) or [None])[-1]

    def last_maintenance_date(self):
        last = self.last_maintenance()
        return last.date_performed.date() if last else None

    def last_backup(self):
        return (sorted(self.backups, key=lambda b: b.date_performed) or [None])[-1]

    def __repr__(self):
        return f"<PC {self.name}>"

class Maintenance(db.Model):
    __tablename__ = "maintenances"
    id = db.Column(db.Integer, primary_key=True)
    pc_id = db.Column(db.Integer, db.ForeignKey("pcs.id"), nullable=False)
    date_performed = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    performed_by = db.Column(db.String(120))
    description = db.Column(db.Text)

class Backup(db.Model):
    __tablename__ = "backups"
    id = db.Column(db.Integer, primary_key=True)
    pc_id = db.Column(db.Integer, db.ForeignKey("pcs.id"), nullable=False)
    date_performed = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(50), default="OK")
    size_mb = db.Column(db.Float)
    path = db.Column(db.String(255))

class Alert(db.Model):
    __tablename__ = "alerts"
    id = db.Column(db.Integer, primary_key=True)
    pc_id = db.Column(db.Integer, db.ForeignKey("pcs.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    kind = db.Column(db.String(50), default="maintenance")  # maintenance | backup
    message = db.Column(db.String(255), nullable=False)
    resolved = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime, nullable=True)

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="user")

    @classmethod
    def create_user(cls, username, password, role="user"):
        u = cls(username=username, password_hash=generate_password_hash(password), role=role)
        db.session.add(u); db.session.commit(); return u

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class ChangeLog(db.Model):
    __tablename__ = "changelog"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    username = db.Column(db.String(80))
    action = db.Column(db.String(50))
    entity = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)

class Config(db.Model):
    __tablename__ = "config"
    id = db.Column(db.Integer, primary_key=True)
    # SMTP
    smtp_host = db.Column(db.String(200))
    smtp_port = db.Column(db.Integer, default=587)
    smtp_tls = db.Column(db.Boolean, default=True)
    smtp_user = db.Column(db.String(200))
    smtp_pass = db.Column(db.String(300))
    mail_from = db.Column(db.String(200))
    mail_to = db.Column(db.String(500))  # coma separada
    # Alertas
    maintenance_days = db.Column(db.Integer, default=7)
    backup_days = db.Column(db.Integer, default=7)
    alerts_enabled = db.Column(db.Boolean, default=True)
    summary_daily = db.Column(db.Boolean, default=False)

class EmailLog(db.Model):
    __tablename__ = "email_logs"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    subject = db.Column(db.String(255))
    recipients = db.Column(db.String(500))
    ok = db.Column(db.Boolean, default=False)
    info = db.Column(db.Text)
    error = db.Column(db.Text)

TASK_STATUS_CHOICES = ("pendiente", "en_progreso", "finalizada")
TASK_PRIORITY_CHOICES = ("baja", "media", "alta")

class Task(db.Model):
    __tablename__ = "task"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)  # título/tema de la tarea
    pc_id = db.Column(db.Integer, db.ForeignKey("pcs.id"), nullable=True)  # opcional: asociar a una PC
    status = db.Column(db.String(20), default="pendiente", index=True)
    priority = db.Column(db.String(10), default="media", index=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    problem = db.Column(db.Text, nullable=False)       # descripción del problema
    solution = db.Column(db.Text, nullable=True)       # cuál fue la solución (si hubo)
    comments = db.Column(db.Text, nullable=True)       # comentarios varios
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


    pc = db.relationship("PC", backref=db.backref("tasks", lazy="dynamic"))
    attachments = db.relationship("TaskAttachment", backref="task", cascade="all, delete-orphan", lazy="dynamic")

    def __repr__(self):
        return f"<Task {self.id} {self.title!r}>"

class TaskAttachment(db.Model):
    __tablename__ = "task_attachment"
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)      # nombre guardado en disco (único)
    original_name = db.Column(db.String(255), nullable=True)  # nombre original para mostrar
    content_type = db.Column(db.String(100), nullable=True)
    size = db.Column(db.Integer, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    uploader_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # opcional

    def __repr__(self):
        return f"<TaskAttachment {self.id} {self.original_name!r}>"