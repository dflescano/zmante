from flask import Blueprint, send_file, request
from io import BytesIO
from datetime import datetime, timedelta
from flask_login import login_required, current_user
from .models import PC, Maintenance, Backup
from .utils import pcs_to_workbook, activity_to_workbook, activity_to_pdf

bp = Blueprint("export", __name__)

def parse_dates():
    s = request.args.get("start"); e = request.args.get("end")
    def norm(val):
        if val is None: return None
        val = str(val).strip().lower()
        if val in ("", "undefined", "null", "none"): return None
        try:
            return datetime.strptime(val, "%Y-%m-%d")
        except Exception:
            return None
    start = norm(s); end = norm(e)
    if start and end and start > end: start, end = end, start
    if end: end = end + timedelta(days=1)
    return start, end

@bp.route("/excel")
@login_required
def excel():
    if current_user.role != "admin":
        return ("Solo admin puede exportar.", 403)
    from .models import Config
    cfg = Config.query.get(1)
    maint_days = cfg.maintenance_days if cfg else 7
    wb = pcs_to_workbook(PC.query.order_by(PC.name.asc()).all(), maint_days=maint_days)
    bio = BytesIO(); wb.save(bio); bio.seek(0)
    return send_file(bio, as_attachment=True, download_name=f"pcs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@bp.route("/actividad/excel")
@login_required
def actividad_excel():
    start, end = parse_dates()
    q_m = Maintenance.query
    q_b = Backup.query
    if start: q_m = q_m.filter(Maintenance.date_performed >= start); q_b = q_b.filter(Backup.date_performed >= start)
    if end: q_m = q_m.filter(Maintenance.date_performed < end); q_b = q_b.filter(Backup.date_performed < end)
    wb = activity_to_workbook(q_m.order_by(Maintenance.date_performed.desc()).all(),
                              q_b.order_by(Backup.date_performed.desc()).all())
    bio = BytesIO(); wb.save(bio); bio.seek(0)
    return send_file(bio, as_attachment=True, download_name=f"actividad_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@bp.route("/actividad/pdf")
@login_required
def actividad_pdf():
    start, end = parse_dates()
    q_m = Maintenance.query
    q_b = Backup.query
    if start: q_m = q_m.filter(Maintenance.date_performed >= start); q_b = q_b.filter(Backup.date_performed >= start)
    if end: q_m = q_m.filter(Maintenance.date_performed < end); q_b = q_b.filter(Backup.date_performed < end)
    bio = activity_to_pdf(q_m.order_by(Maintenance.date_performed.desc()).all(),
                          q_b.order_by(Backup.date_performed.desc()).all())
    bio.seek(0)
    return send_file(bio, as_attachment=True, download_name=f"actividad_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf", mimetype="application/pdf")
