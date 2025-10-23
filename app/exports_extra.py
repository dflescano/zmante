# app/exports_extra.py
from flask import Blueprint, send_file, make_response
from flask_login import login_required
from io import BytesIO
from datetime import datetime, date, time
from markupsafe import escape

from .models import Task, PC

bp = Blueprint("exportx", __name__)

# ---- Helpers de fechas/horas ----

def _as_date(x):
    """Devuelve siempre date (YYYY-MM-DD). None -> date.max."""
    if x is None:
        return date.max
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    # strings u otros: intentar parsear a date
    s = str(x).strip().replace("/", "-")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.date()
        except Exception:
            pass
    return date.max

def _as_dt(x):
    """Devuelve siempre datetime. None -> datetime.max."""
    if x is None:
        return datetime.max
    if isinstance(x, datetime):
        return x
    if isinstance(x, date):
        return datetime.combine(x, time())
    # strings u otros: intentar parsear a datetime (o fallback a max)
    s = str(x).strip().replace("/", "-")
    for fmt in ("%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(s, fmt)
            if fmt in ("%Y-%m-%d", "%d-%m-%Y"):
                dt = datetime.combine(dt.date(), time())
            return dt
        except Exception:
            pass
    return datetime.max

def _fmt_dt(dt):
    """Devuelve string de fecha/hora en horario local (si hay helper disponible)."""
    try:
        from .time_helpers import to_local
        if dt is None:
            return ""
        loc = to_local(dt)
        return loc.strftime("%Y-%m-%d %H:%M")
    except Exception:
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d %H:%M")
        if isinstance(dt, date):
            return datetime.combine(dt, time()).strftime("%Y-%m-%d %H:%M")
        # intentar parseo
        try:
            return _as_dt(dt).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return ""

def _fmt_date_only(d):
    """Formatea date/datetime/string a YYYY-MM-DD."""
    if d is None:
        return ""
    if isinstance(d, datetime):
        return d.date().strftime("%Y-%m-%d")
    if isinstance(d, date):
        return d.strftime("%Y-%m-%d")
    # intentar parseo
    try:
        return _as_date(d).strftime("%Y-%m-%d")
    except Exception:
        return str(d)

def _norm_status(s: str) -> str:
    """Mapea estados legacy al set visual actual."""
    if not s:
        return ""
    s0 = s.strip().lower()
    mapping = {
        "pendiente": "Pendiente",
        "en progreso": "En progreso",
        "en_progreso": "En progreso",
        "progreso": "En progreso",
        "hecho": "Finalizada",
        "finalizado": "Finalizada",
        "finalizada": "Finalizada",
        "cerrado": "Finalizada",
        "ok": "Finalizada",
        "done": "Finalizada",
    }
    return mapping.get(s0, s.capitalize())

def _safe_capitalize(x, default=""):
    v = (x or default)
    try:
        return str(v).capitalize()
    except Exception:
        return str(v)

# ---- Render XLS/HTML ----

def _excel_html(filename: str, title: str, headers, rows):
    """Genera un .xls (HTML de compatibilidad)."""
    headers_html = ''.join(f"<th>{escape(h)}</th>" for h in headers)

    def row_html(r):
        cells = ''.join(
            f"<td>{escape(str(c) if c is not None else '')}</td>"
            for c in r
        )
        return f"<tr>{cells}</tr>"

    rows_html = '\n'.join(row_html(r) for r in rows)
    html = f"""<html>
<head><meta charset="utf-8"></head>
<body>
<h3>{escape(title)}</h3>
<table border="1" cellspacing="0" cellpadding="3">
  <tr>{headers_html}</tr>
  {rows_html}
</table>
</body>
</html>"""
    data = html.encode('utf-8')
    resp = make_response(data)
    resp.headers['Content-Type'] = 'application/vnd.ms-excel; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp

# ---- Render PDF (ReportLab) ----

def _pdf_table(title: str, headers, rows):
    """Genera PDF con ReportLab (tabla compacta, títulos repetidos)."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except Exception as e:
        return make_response(f"PDF no disponible: falta reportlab ({e})", 501)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=12, rightMargin=12, topMargin=12, bottomMargin=12
    )
    styles = getSampleStyleSheet()
    pstyle = ParagraphStyle('base', parent=styles['Normal'], fontSize=8, leading=10)

    def P(x):
        if x is None:
            x = ""
        # Paragraph ya espera HTML sencillo; escapamos y preservamos saltos
        return Paragraph(escape(str(x)).replace("\n", "<br/>"), pstyle)

    data = [[P(h) for h in headers]]
    for r in rows:
        data.append([P(c) for c in r])

    tbl = Table(data, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.aliceblue]),
    ]))

    elems = [Paragraph(escape(title), styles['Heading2']), Spacer(1, 6), tbl]
    doc.build(elems)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=f"{title}.pdf")

# ---- Ordenamiento consistente (evita comparar date vs datetime) ----

def _sort_key_task(t):
    """
    Orden: fecha de inicio (o creada si falta) asc; nulos al final; luego prioridad; luego id.
    - Unifica tipos usando _as_date/_as_dt para que la tupla tenga tipos comparables.
    """
    sd = getattr(t, "start_date", None)
    ca = getattr(t, "created_at", None)
    due = _as_date(sd) if sd is not None else _as_date(ca)
    # prioridad: num si existe, si es string intentar mapear; nulos altos
    prio = getattr(t, "priority", None)
    prio_val = _priority_value(prio)
    # created como datetime para desempate
    created_dt = _as_dt(ca)
    return (due == date.max, due, prio_val, created_dt, getattr(t, "id", 0))

def _priority_value(p):
    """Normaliza prioridad a un número: menor = más alta. 'alta' < 'media' < 'baja'."""
    if p is None or p == "":
        return 9999
    # num directo
    try:
        return int(p)
    except Exception:
        pass
    s = str(p).strip().lower()
    mapping = {
        "alta": 1, "high": 1, "urgent": 0, "urgente": 0,
        "media": 5, "normal": 5,
        "baja": 9, "low": 9,
    }
    return mapping.get(s, 50)

# =========================
#         RUTAS
# =========================

# ---- TASKS ----

@bp.route('/export/tasks.xls')
@login_required
def export_tasks_xls():
    tasks = Task.query.all()
    tasks_sorted = sorted(tasks, key=_sort_key_task)

    headers = [
        'ID', 'Título', 'PC', 'Estado', 'Prioridad', 'Inicio', 'Fin',
        'Problema', 'Solución', 'Comentarios', 'Creado', 'Actualizado'
    ]
    rows = []
    for t in tasks_sorted:
        pc_name = t.pc.name if getattr(t, 'pc', None) else ''
        rows.append([
            t.id,
            t.title or '',
            pc_name,
            _norm_status(getattr(t, "status", "")),
            _safe_capitalize(getattr(t, "priority", "")),
            _fmt_date_only(getattr(t, "start_date", None)),
            _fmt_date_only(getattr(t, "end_date", None)),
            getattr(t, "problem", "") or '',
            getattr(t, "solution", "") or '',
            getattr(t, "comments", "") or '',
            _fmt_dt(getattr(t, 'created_at', None)),
            _fmt_dt(getattr(t, 'updated_at', None)),
        ])
    return _excel_html('tareas.xls', 'Reporte de Tareas', headers, rows)

@bp.route('/export/tasks.pdf')
@login_required
def export_tasks_pdf():
    tasks = Task.query.all()
    tasks_sorted = sorted(tasks, key=_sort_key_task)

    headers = [
        'ID', 'Título', 'PC', 'Estado', 'Prioridad', 'Inicio', 'Fin',
        'Problema', 'Solución', 'Comentarios', 'Creado', 'Actualizado'
    ]
    rows = []
    for t in tasks_sorted:
        pc_name = t.pc.name if getattr(t, 'pc', None) else ''
        rows.append([
            t.id,
            t.title or '',
            pc_name,
            _norm_status(getattr(t, "status", "")),
            _safe_capitalize(getattr(t, "priority", "")),
            _fmt_date_only(getattr(t, "start_date", None)),
            _fmt_date_only(getattr(t, "end_date", None)),
            getattr(t, "problem", "") or '',
            getattr(t, "solution", "") or '',
            getattr(t, "comments", "") or '',
            _fmt_dt(getattr(t, 'created_at', None)),
            _fmt_dt(getattr(t, 'updated_at', None)),
        ])
    return _pdf_table('Reporte de Tareas', headers, rows)

# ---- PCS ----

@bp.route('/export/pcs.xls')
@login_required
def export_pcs_xls():
    pcs = PC.query.order_by(PC.name.asc()).all()
    headers = [
        'ID', 'Nombre PC', 'Usuario PC', 'Usuario físico', 'Teamviewer', 'Anydesk',
        'Windows Legal', 'Office Legal', 'Observaciones',
        'Últ. Mantenimiento', 'Últ. Backup',
        'Creado', 'Actualizado'
    ]
    rows = []
    for p in pcs:
        # último mantenimiento
        try:
            last_m = p.last_maintenance_date()
        except Exception:
            last_m = None
        # último backup (si el método retorna objeto con fecha)
        try:
            lb = p.last_backup()
            if lb is None:
                last_b = None
            else:
                # aceptar lb como date, datetime o con atributo date_performed
                if hasattr(lb, "date_performed"):
                    last_b = getattr(lb, "date_performed", None)
                else:
                    last_b = lb
        except Exception:
            last_b = None

        rows.append([
            p.id,
            p.name or '',
            getattr(p, 'pc_user', '') or '',
            getattr(p, 'physical_user', '') or '',
            getattr(p, 'teamviewer', '') or '',
            getattr(p, 'anydesk', '') or '',
            'Sí' if getattr(p, 'windows_legal', False) else 'No',
            'Sí' if getattr(p, 'office_legal', False) else 'No',
            getattr(p, 'observations', '') or '',
            _fmt_date_only(last_m),
            _fmt_date_only(last_b),
            _fmt_dt(getattr(p, 'created_at', None)),
            _fmt_dt(getattr(p, 'updated_at', None)),
        ])
    return _excel_html('pcs.xls', 'Reporte de PCs', headers, rows)

@bp.route('/export/pcs.pdf')
@login_required
def export_pcs_pdf():
    pcs = PC.query.order_by(PC.name.asc()).all()
    headers = [
        'ID', 'Nombre PC', 'Usuario PC', 'Usuario físico', 'Teamviewer', 'Anydesk',
        'Windows Legal', 'Office Legal', 'Observaciones',
        'Últ. Mantenimiento', 'Últ. Backup',
        'Creado', 'Actualizado'
    ]
    rows = []
    for p in pcs:
        try:
            last_m = p.last_maintenance_date()
        except Exception:
            last_m = None
        try:
            lb = p.last_backup()
            if lb is None:
                last_b = None
            else:
                if hasattr(lb, "date_performed"):
                    last_b = getattr(lb, "date_performed", None)
                else:
                    last_b = lb
        except Exception:
            last_b = None

        rows.append([
            p.id,
            p.name or '',
            getattr(p, 'pc_user', '') or '',
            getattr(p, 'physical_user', '') or '',
            getattr(p, 'teamviewer', '') or '',
            getattr(p, 'anydesk', '') or '',
            'Sí' if getattr(p, 'windows_legal', False) else 'No',
            'Sí' if getattr(p, 'office_legal', False) else 'No',
            getattr(p, 'observations', '') or '',
            _fmt_date_only(last_m),
            _fmt_date_only(last_b),
            _fmt_dt(getattr(p, 'created_at', None)),
            _fmt_dt(getattr(p, 'updated_at', None)),
        ])
    return _pdf_table('Reporte de PCs', headers, rows)
