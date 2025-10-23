
from datetime import datetime
from flask import Blueprint, current_app, render_template
try:
    from zoneinfo import ZoneInfo
except Exception:
    try:
        import pytz
        ZoneInfo = pytz.timezone
    except Exception:
        ZoneInfo = None

bp = Blueprint("diag", __name__, template_folder="templates", url_prefix="/diagnostico")

@bp.route("/horario")
def horario():
    tz = current_app.config.get("APP_TZ")
    tz_name = current_app.config.get("TZ_NAME")
    try:
        utc = ZoneInfo("UTC") if ZoneInfo else None
    except Exception:
        utc = None
    data = {
        "tz_name": tz_name,
        "server_now_naive": datetime.now(),
        "app_now_local": datetime.now(tz) if tz else "N/A",
        "utc_now": datetime.now(utc) if utc else "N/A",
    }
    return render_template("diag_time.html", **data)
