PARCHE — XLSX nativo para Tareas y PCs
======================================

Este archivo **reemplaza** tu `app/exports_extra.py` anterior y agrega endpoints .xlsx reales
(usa openpyxl). Mantiene también los endpoints .xls y .pdf que ya venías usando.

Nuevos endpoints
----------------
- /export/tasks.xlsx
- /export/pcs.xlsx

También siguen disponibles:
- /export/tasks.xls   (modo compatibilidad HTML)
- /export/tasks.pdf   (requiere reportlab)
- /export/pcs.xls
- /export/pcs.pdf

Instalación
-----------
1) Copiá `app/exports_extra.py` de este parche sobre tu archivo actual.
2) Reiniciá la app.
3) Asegurate de tener **openpyxl**:
   `pip install openpyxl`

Enlaces en plantillas
---------------------
Tareas:
  <a href="{{ url_for('exportx.export_tasks_xlsx') }}" class="btn">Excel (XLSX)</a>

PCs:
  <a href="{{ url_for('exportx.export_pcs_xlsx') }}" class="btn">Excel (XLSX)</a>

Notas
-----
- Si openpyxl no está instalado, el endpoint devuelve 501 con un mensaje.
- Las fechas se formatean en hora local si `time_helpers.to_local` existe.
- Si venías usando `reports.tasks_xlsx`, podés mantenerlo o cambiar tus botones
  a los nuevos endpoints de este blueprint.
