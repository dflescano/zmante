PARCHE — Exportar Tareas y PCs a Excel (XLS) y PDF (sin romper nada)
===================================================================

Este parche agrega **nuevas rutas de exportación** en un blueprint separado,
para no tocar tu `exports.py` existente.

Qué agrega
----------
- /export/tasks.xls  → Excel (formato .xls compatible, sin dependencias)
- /export/tasks.pdf  → PDF con tabla (usa reportlab)
- /export/pcs.xls    → Excel (formato .xls compatible, sin dependencias)
- /export/pcs.pdf    → PDF con tabla (usa reportlab)

Archivos a copiar
-----------------
1) Copiá `app/exports_extra.py` dentro de tu proyecto.

2) En `app/__init__.py`, **registrá el blueprint** (dos líneas):

    from .exports_extra import bp as exportx_bp
    app.register_blueprint(exportx_bp)   # comparte el prefijo /export internamente

   *Si preferís un prefijo explícito:*
    app.register_blueprint(exportx_bp, url_prefix="/export")

Requisitos
----------
- Para **Excel** (.xls): no se requiere nada extra (se genera HTML que Excel abre como .xls).
- Para **PDF**: se usa **reportlab**. Si no está instalado, la ruta devuelve 501 con un mensaje.
  (Sugerencia: `pip install reportlab`).

Notas
-----
- Las fechas se formatean en **hora local** si existe `time_helpers.to_local` en tu app.
- Los nombres de campos de PC (`pc_user`, `physical_user`, etc.) podés ajustarlos en
  `exports_extra.py` si en tu `models.py` tienen otro nombre exacto.
- Esto **no elimina** ni **modifica** tus exportaciones CSV actuales; suma opciones nuevas.

Opcional: enlaces en la UI
--------------------------
En tus listas (tareas/pcs), podés agregar botones:

Tareas:
  <a href="{{ url_for('exportx.export_tasks_xls') }}" class="btn">Excel</a>
  <a href="{{ url_for('exportx.export_tasks_pdf') }}" class="btn">PDF</a>

PCs:
  <a href="{{ url_for('exportx.export_pcs_xls') }}" class="btn">Excel</a>
  <a href="{{ url_for('exportx.export_pcs_pdf') }}" class="btn">PDF</a>
