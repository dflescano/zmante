PARCHE: TZ/horarios y gestión de alertas + limpiar logs (zmante9)

Archivos para COPIAR SOBRE tu proyecto:
---------------------------------------
1) app/time_helpers.py            (reemplazo completo)
2) app/templates/alerts.html      (reemplazo completo)
3) app/templates/admin_email_logs.html  (reemplazo completo)

Cambios mínimos a Pegar (si no los tenés):
------------------------------------------
A) En app/routes.py
   - Abrí snippets/ROUTES_ALERTS_BLOCK.txt y pegá ese bloque para las rutas de alertas
     (lista y resolver). Si ya tenés esas rutas, solo verificá que 'resolved_at'
     se setee con now_utc() y que la plantilla use el filtro |localtime.

B) En app/admin.py (blueprint 'admin')
   - Abrí snippets/ADMIN_EMAIL_LOGS_ROUTES.txt y pegá esas rutas si no existen:
     * /admin/email-logs                (listado)
     * /admin/email-logs/clear [POST]   (limpiar todos)
     * /admin/alerts/<id>/delete [POST] (eliminar alerta - solo admin)

Requisitos de configuración en create_app():
-------------------------------------------
app.config["TZ_NAME"]  = os.environ.get("TZ_NAME", "America/Argentina/Buenos_Aires")
app.config["APP_TZ"]   = ZoneInfo(app.config["TZ_NAME"])
app.config["NAIVE_AS"] = os.environ.get("NAIVE_AS", "LOCAL")  # naive -> LOCAL

Registro del filtro de hora local (ya deberías tenerlo):
--------------------------------------------------------
from .time_helpers import to_local

def _fmt_local(dt, fmt="%Y-%m-%d %H:%M"):
    dt = to_local(dt)
    return dt.strftime(fmt) if dt else ""
app.jinja_env.filters["localtime"] = _fmt_local

Modelos (verifica defaults en UTC):
-----------------------------------
- EmailLog.created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
- Alert.created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
- Alert.resolved_at   = db.Column(db.DateTime, nullable=True)

Templates: uso de filtro
------------------------
- En alerts.html y admin_email_logs.html ya se usa {{ x|localtime("...") }}

Eso es todo. Copiá los 3 archivos y, si hace falta, pega los bloques de snippets
en routes.py y admin.py.
