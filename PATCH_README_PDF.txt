PARCHE — PDF mejor distribuido + XLSX
======================================

Este archivo reemplaza tu `app/exports_extra.py` e introduce un generador de PDF
con **ancho de columnas calculado** y **wrap de texto** usando Paragraphs.

- TAREAS: usa `mode="tasks"` con fracciones de ancho pensadas para Problema/Solución/Comentarios.
- PCs: usa `mode="pcs"` con fracciones adecuadas.

Instalación
-----------
1) Copiá `app/exports_extra.py` de este parche sobre tu archivo actual.
2) Reiniciá la app.
3) Asegurate de tener `reportlab` para PDF y `openpyxl` para XLSX:
   pip install reportlab openpyxl

Endpoints
---------
- /export/tasks.pdf   (mejor distribución)
- /export/tasks.xlsx
- /export/tasks.xls   (compatibilidad)
- /export/pcs.pdf
- /export/pcs.xlsx
- /export/pcs.xls
