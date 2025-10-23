
import io, csv, unicodedata
from datetime import datetime
from typing import List, Dict, Any, Optional
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file
from flask_login import login_required
from .models import Task
from . import db

bp = Blueprint("tasksimp", __name__, template_folder="templates", url_prefix="/tasks")

def _norm(s: Optional[str]) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return s.lower()

def _parse_date(val: Any) -> Optional[datetime.date]:
    if val is None: return None
    s = str(val).strip()
    if not s: return None
    if isinstance(val, datetime):
        return val.date()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None

_HEADERS = {
    "title":      ["titulo","título","title","asunto","nombre"],
    "start_date": ["fecha_inicio","fecha de inicio","inicio","start","start_date"],
    "end_date":   ["fecha_fin","fecha de fin","fin","end","end_date"],  # opcional
    "status":     ["estado","status"],
    "priority":   ["prioridad","priority"],
    "comments":   ["comentarios","descripcion","descripción","description","notas","notes"],
    "problem":    ["problema","problem"],             # si no viene, se rellena con comentarios/título
    "solution":   ["solucion","solución","solution"], # opcional
    # (opcional para asociar PC)
    # "pc_id":   ["pc_id","id_pc"],
    # "pc_name": ["pc","pcname","pc_name","equipo"],
}


def _match_header_map(headers: List[str]) -> Dict[str, str]:
    out = {}
    norm_headers = { _norm(h): h for h in headers }
    for field, aliases in _HEADERS.items():
        for al in aliases:
            if _norm(al) in norm_headers:
                out[field] = norm_headers[_norm(al)]
                break
    return out

def _normalize_status(s: str) -> str:
    n = _norm(s)
    if not n: return ""
    if n in ("pendiente","pending","todo"):
        return "pendiente"
    if n in ("en progreso","en_progreso","in progress","doing","progreso"):
        return "en progreso"
    if n in ("finalizada","final","done","completed","completado","cerrado","hecho"):
        return "finalizada"
    return s


def _normalize_priority(s: str) -> str:
    n = _norm(s)
    if not n: return ""
    if n in ("baja","low"): return "baja"
    if n in ("media","medio","medium","normal"): return "media"
    if n in ("alta","high","urgente","urgent"): return "alta"
    return s

def _set_if_has(obj, field_name, value):
    if hasattr(obj, field_name):
        setattr(obj, field_name, value)

def _read_xlsx(file_storage) -> List[Dict[str, Any]]:
    try:
        from openpyxl import load_workbook
    except Exception:
        raise RuntimeError("Para .xlsx instalá: pip install openpyxl")
    f = io.BytesIO(file_storage.read())
    wb = load_workbook(f, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.rows)
    if not rows:
        return []
    headers = [ (c.value or "").strip() if isinstance(c.value, str) else (c.value or "") for c in rows[0] ]
    out = []
    for r in rows[1:]:
        rec = {}
        for i, c in enumerate(r):
            key = headers[i] if i < len(headers) else f"col{i}"
            rec[key] = c.value
        out.append(rec)
    return out

def _read_csv(file_storage) -> List[Dict[str, Any]]:
    text = file_storage.read().decode("utf-8", errors="ignore")
    return list(csv.DictReader(io.StringIO(text)))

# rutas

@bp.route("/import", methods=["GET"])
@login_required
def import_form():
    expected = {
        "Obligatorios": ["titulo", "fecha_inicio", "estado", "prioridad", "comentarios"],
        "Opcional": ["fecha_fin"]
    }

    # construir back_url en Python (no en Jinja)
    has_tasks_list = "main.tasks_list" in current_app.view_functions
    back_url = url_for("main.tasks_list") if has_tasks_list else url_for("main.index")

    return render_template("tasks_import.html", expected=expected, back_url=back_url)


@bp.route("/import/sample.csv", methods=["GET"])
@login_required
def import_sample():
    sample = (
        "titulo,fecha_inicio,estado,prioridad,comentarios,fecha_fin\n"
        "Instalar Office,2025-01-20,pendiente,alta,Instalar Office 365 en PC Juan,2025-01-21\n"
        "Configurar backup,20/01/2025,en progreso,media,Revisar destino NAS,\n"
    ).encode("utf-8")
    return send_file(io.BytesIO(sample), mimetype="text/csv", as_attachment=True, download_name="tareas_ejemplo.csv")

@bp.route("/import", methods=["POST"])
@login_required
def import_run():
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Subí un archivo .xlsx o .csv", "warning")
        return redirect(url_for("tasksimp.import_form"))

    fn = file.filename.lower()
    try:
        if fn.endswith(".xlsx"):
            rows = _read_xlsx(file)
        else:
            rows = _read_csv(file)
    except Exception as e:
        flash(f"Error leyendo archivo: {e}", "danger")
        return redirect(url_for("tasksimp.import_form"))

    if not rows:
        flash("El archivo no tiene filas.", "warning")
        return redirect(url_for("tasksimp.import_form"))

    headers = list(rows[0].keys())
    hmap = _match_header_map(headers)

    inserted = 0
    errors = 0

    for r in rows:
        try:
            t = Task()

            # ---- título ----
            title = r.get(hmap.get("title",""), "") if "title" in hmap else (r.get("title") or r.get("titulo") or "")
            title = (str(title).strip() if title is not None else "")
            if hasattr(Task, "title"):
                t.title = title
            elif hasattr(Task, "name"):
                t.name = title

            # ---- fechas ----
            start = _parse_date(r.get(hmap.get("start_date","")))
            end   = _parse_date(r.get(hmap.get("end_date","")))
            if hasattr(Task, "start_date"):
                t.start_date = start
            if hasattr(Task, "end_date"):
                t.end_date = end

            # ---- estado ----
            status = r.get(hmap.get("status",""), "")
            status = _normalize_status(status)
            _set_if_has(t, "status", status or "pendiente")

            # ---- prioridad ----
            prio = r.get(hmap.get("priority",""), "")
            prio = _normalize_priority(prio)
            _set_if_has(t, "priority", prio or "media")

            # ---- comentarios / descripción ----
            comments = r.get(hmap.get("comments",""), "")
            comments = "" if comments is None else str(comments)
            if hasattr(Task, "comments"):
                t.comments = comments
            elif hasattr(Task, "description"):
                t.description = comments

            # ---- problema / solución (problem es NOT NULL) ----
            prob = r.get(hmap.get("problem",""), "")
            sol  = r.get(hmap.get("solution",""), "")
            prob = "" if prob is None else str(prob).strip()
            sol  = "" if  sol is None else str(sol).strip()

            # Fallback fuerte: NUNCA None
            problem_value = prob or (comments.strip() if comments else "") or (title if title else "N/A")
            # set explícito (sin hasattr): sabemos que existe porque falla el NOT NULL
            try:
                t.problem = problem_value
            except Exception:
                # por si el modelo usa otro nombre, último fallback
                setattr(t, "problem", problem_value)

            if hasattr(Task, "solution"):
                t.solution = sol

            # ---- (Opcional) asociar PC por id o nombre) ----
            # from .models import PC
            # if "pc_id" in hmap:
            #     pcv = r.get(hmap["pc_id"])
            #     if pcv and hasattr(Task, "pc_id"):
            #         try: t.pc_id = int(pcv)
            #         except: pass
            # elif "pc_name" in hmap:
            #     name = str(r.get(hmap["pc_name"], "") or "").strip()
            #     if name:
            #         pc = PC.query.filter(PC.name.ilike(name)).first()
            #         if pc and hasattr(Task, "pc_id"):
            #             t.pc_id = pc.id

            db.session.add(t)
            db.session.flush()   # <--- valida esta fila ya mismo
            inserted += 1

        except Exception:
            errors += 1
            db.session.rollback()
            continue

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Error al confirmar cambios: {e}", "danger")
        return redirect(url_for("tasksimp.import_form"))

    flash(f"Importación finalizada: {inserted} tareas creadas, {errors} con error.", "success")
    dest = "main.tasks_list" if "main.tasks_list" in current_app.view_functions else "main.index"
    return redirect(url_for(dest))

