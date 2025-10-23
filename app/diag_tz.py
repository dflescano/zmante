# app/diag_tz.py
from flask import Blueprint, current_app
from .time_helpers import now_local

bp = Blueprint("diag", __name__)

@bp.route("/horario")
def horario():
    n = now_local()
    tz = current_app.config.get("TZ_NAME", "America/Argentina/Buenos_Aires")
    return f"TZ_NAME={tz} | now_local={n.isoformat()}"
