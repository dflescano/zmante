
import csv, io
from collections import Counter
from datetime import datetime, date
from flask import Blueprint, render_template, request
from flask_login import login_required
from .models import PC, Task, Config
from .utils_export import stream_csv, stream_xlsx, stream_pdf

bp = Blueprint("reports", __name__, template_folder="templates")

def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date() if s else None
    except Exception:
        return None

def get_thresholds():
    cfg = Config.query.get(1)
    maint_days = int(cfg.maintenance_days or 7) if cfg else 7
    backup_days = int(cfg.backup_days or 7) if cfg else 7
    return maint_days, backup_days

def pc_last_dates(pc):
    lm = pc.last_maintenance_date()
    lb_obj = pc.last_backup()
    lb = lb_obj.date_performed.date() if lb_obj else None
    return lm, lb

def pc_age_or_start_days(pc, maybe_date):
    from .utils import pc_created_date
    start = maybe_date or pc_created_date(pc)
    return (date.today() - start).days

@bp.route("/", strict_slashes=False)
@bp.route("", strict_slashes=False)
@login_required
def dashboard():
    maint_days, backup_days = get_thresholds()
    total_tasks = Task.query.count()
    status_counts = Counter((t.status or "—") for t in Task.query.all())
    priority_counts = Counter((t.priority or "—") for t in Task.query.all())

    finished = Task.query.filter(Task.status == "finalizada").all()
    def resolved_days(t):
        s = t.start_date or (t.created_at.date() if t.created_at else None)
        e = t.end_date or (t.updated_at.date() if t.updated_at else None)
        if s and e: return max((e - s).days, 0)
        return None
    vals = [d for t in finished for d in [resolved_days(t)] if d is not None]
    avg_resolve = (sum(vals) / len(vals)) if vals else None

    pcs = PC.query.all()
    pcs_alert_m = pcs_alert_b = 0
    for pc in pcs:
        lm, lb = pc_last_dates(pc)
        if pc_age_or_start_days(pc, lm) >= maint_days: pcs_alert_m += 1
        if pc_age_or_start_days(pc, lb) >= backup_days: pcs_alert_b += 1

    return render_template("reports_dashboard.html",
                           total_tasks=total_tasks,
                           status_counts=status_counts,
                           priority_counts=priority_counts,
                           avg_resolve=avg_resolve,
                           pcs_total=len(pcs),
                           pcs_alert_m=pcs_alert_m,
                           pcs_alert_b=pcs_alert_b,
                           maint_days=maint_days,
                           backup_days=backup_days)

@bp.route("/tasks")
@login_required
def tasks_report():
    start = parse_date(request.args.get("start"))
    end = parse_date(request.args.get("end"))
    q = Task.query
    if start: q = q.filter(Task.created_at >= datetime.combine(start, datetime.min.time()))
    if end: q = q.filter(Task.created_at <= datetime.combine(end, datetime.max.time()))
    tasks = q.order_by(Task.created_at.desc()).all()

    by_status = Counter((t.status or "—") for t in tasks)
    by_priority = Counter((t.priority or "—") for t in tasks)
    by_pc = Counter((t.pc.name if t.pc else "—") for t in tasks)

    by_month = Counter()
    for t in tasks:
        dt = t.created_at.date() if t.created_at else None
        if not dt: continue
        key = f"{dt.year}-{dt.month:02d}"
        by_month[key] += 1
    months_sorted = sorted(by_month.keys())

    return render_template("report_tasks.html",
                           tasks=tasks,
                           start=start, end=end,
                           by_status=by_status,
                           by_priority=by_priority,
                           by_pc=by_pc.most_common(20),
                           months=months_sorted,
                           series=[by_month[m] for m in months_sorted])

@bp.route("/tasks.csv")
@login_required
def tasks_csv():
    start = parse_date(request.args.get("start")); end = parse_date(request.args.get("end"))
    q = Task.query
    if start: q = q.filter(Task.created_at >= datetime.combine(start, datetime.min.time()))
    if end: q = q.filter(Task.created_at <= datetime.combine(end, datetime.max.time()))
    tasks = q.order_by(Task.created_at.desc()).all()

    headers = ["id","title","status","priority","pc","start_date","end_date","created_at","updated_at"]
    rows = [[t.id, t.title, t.status, t.priority, (t.pc.name if t.pc else ""),
            t.start_date or "", t.end_date or "", t.created_at or "", t.updated_at or ""]
    for t in tasks]
    return stream_csv("tasks_report.csv", headers, rows)

@bp.route("/tasks.xlsx")
@login_required
def tasks_xlsx():
    start = parse_date(request.args.get("start")); end = parse_date(request.args.get("end"))
    q = Task.query
    if start: q = q.filter(Task.created_at >= datetime.combine(start, datetime.min.time()))
    if end: q = q.filter(Task.created_at <= datetime.combine(end, datetime.max.time()))
    tasks = q.order_by(Task.created_at.desc()).all()

    headers = ["id","title","status","priority","pc","start_date","end_date","created_at","updated_at"]
    rows = [[t.id, t.title, t.status, t.priority, (t.pc.name if t.pc else ""),
            t.start_date or "", t.end_date or "", t.created_at or "", t.updated_at or ""]
    for t in tasks]
    return stream_xlsx("tasks_report.xlsx", headers, rows)

@bp.route("/tasks.pdf")
@login_required
def tasks_pdf():
    start = parse_date(request.args.get("start")); end = parse_date(request.args.get("end"))
    q = Task.query
    if start: q = q.filter(Task.created_at >= datetime.combine(start, datetime.min.time()))
    if end: q = q.filter(Task.created_at <= datetime.combine(end, datetime.max.time()))
    tasks = q.order_by(Task.created_at.desc()).all()

    headers = ["ID","Título","Estado","Prioridad","PC","Inicio","Fin"]
    rows = [[t.id, t.title, t.status, t.priority, (t.pc.name if t.pc else ""),
            t.start_date or "", t.end_date or ""]
    for t in tasks]
    return stream_pdf("tasks_report.pdf", "Reporte de Tareas", headers, rows)

@bp.route("/pcs")
@login_required
def pcs_report():
    maint_days, backup_days = get_thresholds()
    only_alerts = (request.args.get("alerts") == "1")

    rows = []
    for pc in PC.query.order_by(PC.name.asc()).all():
        lm = pc.last_maintenance_date()
        lb_obj = pc.last_backup()
        lb = lb_obj.date_performed.date() if lb_obj else None
        age_m = pc_age_or_start_days(pc, lm)
        age_b = pc_age_or_start_days(pc, lb)
        alert_m = (age_m >= maint_days)
        alert_b = (age_b >= backup_days)
        if only_alerts and not (alert_m or alert_b):
            continue
        rows.append({"pc": pc, "lm": lm, "lb": lb, "age_m": age_m, "age_b": age_b,
                     "alert_m": alert_m, "alert_b": alert_b})

    return render_template("report_pcs.html",
                           rows=rows, maint_days=maint_days, backup_days=backup_days, only_alerts=only_alerts)

@bp.route("/pcs.csv")
@login_required
def pcs_csv():
    maint_days, backup_days = get_thresholds()
    only_alerts = (request.args.get("alerts") == "1")
    headers = ["pc","usuario","ult_mant","dias_mant","alerta_mant","ult_backup","dias_backup","alerta_backup"]
    rows = []
    for pc in PC.query.order_by(PC.name.asc()).all():
        lm = pc.last_maintenance_date()
        lb_obj = pc.last_backup()
        lb = lb_obj.date_performed.date() if lb_obj else None
        age_m = pc_age_or_start_days(pc, lm)
        age_b = pc_age_or_start_days(pc, lb)
        alert_m = (age_m >= maint_days)
        alert_b = (age_b >= backup_days)
        if only_alerts and not (alert_m or alert_b):
            continue
        rows.append([pc.name,
                     getattr(pc, "user_name", "") or getattr(pc, "user", "") or "",
                     lm or "", age_m, "SI" if alert_m else "NO",
                     lb or "", age_b, "SI" if alert_b else "NO"])
    return stream_csv("pcs_report.csv", headers, rows)

@bp.route("/pcs.xlsx")
@login_required
def pcs_xlsx():
    maint_days, backup_days = get_thresholds()
    only_alerts = (request.args.get("alerts") == "1")
    headers = ["pc","usuario","ult_mant","dias_mant","alerta_mant","ult_backup","dias_backup","alerta_backup"]
    rows = []
    for pc in PC.query.order_by(PC.name.asc()).all():
        lm = pc.last_maintenance_date()
        lb_obj = pc.last_backup()
        lb = lb_obj.date_performed.date() if lb_obj else None
        age_m = pc_age_or_start_days(pc, lm)
        age_b = pc_age_or_start_days(pc, lb)
        alert_m = (age_m >= maint_days)
        alert_b = (age_b >= backup_days)
        if only_alerts and not (alert_m or alert_b):
            continue
        rows.append([pc.name,
                     getattr(pc, "user_name", "") or getattr(pc, "user", "") or "",
                     lm or "", age_m, "SI" if alert_m else "NO",
                     lb or "", age_b, "SI" if alert_b else "NO"])
    return stream_xlsx("pcs_report.xlsx", headers, rows)

@bp.route("/pcs.pdf")
@login_required
def pcs_pdf():
    maint_days, backup_days = get_thresholds()
    only_alerts = (request.args.get("alerts") == "1")
    headers = ["PC","Usuario","Últ. mant.","Días mant.","Alerta mant.","Últ. backup","Días backup","Alerta backup"]
    rows = []
    for pc in PC.query.order_by(PC.name.asc()).all():
        lm = pc.last_maintenance_date()
        lb_obj = pc.last_backup()
        lb = lb_obj.date_performed.date() if lb_obj else None
        age_m = pc_age_or_start_days(pc, lm)
        age_b = pc_age_or_start_days(pc, lb)
        alert_m = (age_m >= maint_days)
        alert_b = (age_b >= backup_days)
        if only_alerts and not (alert_m or alert_b):
            continue
        rows.append([pc.name,
                     getattr(pc, "user_name", "") or getattr(pc, "user", "") or "",
                     lm or "", age_m, "SI" if alert_m else "NO",
                     lb or "", age_b, "SI" if alert_b else "NO"])
    return stream_pdf("pcs_report.pdf", "Reporte de PCs", headers, rows)
