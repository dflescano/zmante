# Sistema de mantenimiento de PC y backups (v3.6 full)

## Incluye
- **Campos completos por PC** (usuario PC, usuario físico, TeamViewer/AnyDesk, licencias, ubicación, observaciones).
- **Historial** de mantenimientos y backups.
- **Login con roles** (admin/user). Admin inicial: `admin / admin` (cambiar con `ADMIN_PASSWORD`).
- **CRUD de PC** solo **admin**. Agregar mantenimiento/backup: cualquier usuario. **Editar/Borrar** mantenimiento/backup: solo **admin**.
- **Alertas automáticas** por **mantenimiento** y por **backup** según umbrales configurables.
- **Configuración persistente** de SMTP y umbrales en DB.
- **Probador de correo** (mail-test) y **logs de envío** (éxitos/errores).
- **Resumen diario** por email con PCs en alerta (opcional).
- **Exportación** de PCs a Excel (solo admin) y actividad (mantenimientos y backups) por rango a Excel/PDF.
- **Auditoría** (ChangeLog) y **filtros** en dashboard.

## Variables de entorno (opcionales)
- `SECRET_KEY`
- `DATABASE_URL` (por defecto SQLite `pc_maintenance.db`)
- `ADMIN_PASSWORD`
- SMTP (fallback si no hay config en DB): `SMTP_HOST`, `SMTP_PORT=587`, `SMTP_TLS=true`, `SMTP_USER`, `SMTP_PASS`, `MAIL_FROM`, `MAIL_TO`
- Resumen diario (hora): `SUMMARY_HOUR=9`, `SUMMARY_MINUTE=0`
- Zona horaria: `TZ_NAME=America/Argentina/Buenos_Aires`

## Instalación
```bat
cd pc_maint_app_v3_6_full
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py run.py
```
Abrí: http://localhost:8000

## Configuración y pruebas
- Ingresá como admin y entrá a **Configuración**: cargá **SMTP**, **MAIL_FROM/MAIL_TO**, y definí **días** para mantenimiento/backup.
- Probá el envío en **Correo (test)**. Revisá resultados en **Logs correo**.
- Si activás **Resumen diario**, se enviará a la hora configurada (por ENV) con el estado de PCs en alerta.
