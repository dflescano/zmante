[PATCH_NOTES.md](https://github.com/user-attachments/files/23098652/PATCH_NOTES.md)
# v3.6.3 — Conteo correcto cuando nunca hubo mantenimiento/backup
Este parche hace que, si una PC **nunca** tuvo mantenimiento o backup, el conteo de días se haga **desde la fecha de creación de la PC** (tomada de la auditoría `ChangeLog`, acción `create`). Corrige:
- Dashboard (Estado)
- Job de alertas automáticas
- Resumen diario por correo

No agrega columnas a la DB.

## Archivos a editar en tu proyecto
1. `app/utils.py`
2. `app/__init__.py`

---

## 1) app/utils.py

**A.** Agregá estos imports (si no están):

```python
from .models import ChangeLog
from datetime import datetime
```

**B.** Agregá este helper (debajo de los imports):

```python
def pc_created_date(pc):
    # Fecha de alta = primer registro de auditoría "create" de esta PC
    cl = (ChangeLog.query
          .filter_by(entity="PC", entity_id=pc.id, action="create")
          .order_by(ChangeLog.created_at.asc())
          .first())
    return cl.created_at.date() if cl else datetime.now().date()
```

**C.** Reemplazá COMPLETO `compute_status` por esta versión:

```python
def compute_status(pc, maint_days=7):
    today = datetime.now().date()
    last = pc.last_maintenance_date()

    if last is None:
        start = pc_created_date(pc)          # <-- cuenta desde el alta
        delta = (today - start).days
        if delta > maint_days:
            return f"SIN MANTENIMIENTO (ALERTA, {delta} días)"
        elif maint_days - 2 <= delta <= maint_days:
            return f"SIN MANTENIMIENTO (POR VENCER, {delta} días)"
        else:
            return f"SIN MANTENIMIENTO ({delta} días)"

    delta = (today - last).days
    if delta > maint_days:
        return f"ALERTA ({delta} días)"
    elif maint_days - 2 <= delta <= maint_days:
        return f"POR VENCER ({delta} días)"
    else:
        return f"OK ({delta} días)"
```

---

## 2) app/__init__.py

**A.** Dentro de `create_app()` (donde ya importás modelos), añadí:

```python
from .utils import pc_created_date
```

**B.** Reemplazá COMPLETO el cuerpo de `check_maintenance_job()` por esto:

```python
def check_maintenance_job():
    from .models import PC, Alert
    with app.app_context():
        vals = get_config_values()
        if not vals.get("ALERTS_ENABLED", True):
            return
        maint_days = vals.get("MAINT_DAYS", 7)
        backup_days = vals.get("BACKUP_DAYS", 7)
        now = datetime.now()
        from datetime import timedelta

        for pc in PC.query.all():
            # --- Maintenance: si nunca hubo, contar desde alta ---
            last_m = pc.last_maintenance_date()                           # date o None
            start_m = last_m or pc_created_date(pc)                        # <-- clave
            need_m_alert = (now.date() - start_m) > timedelta(days=maint_days)

            if need_m_alert:
                existing = Alert.query.filter_by(pc_id=pc.id, resolved=False, kind="maintenance").first()
                if existing is None:
                    a = Alert(pc_id=pc.id, kind="maintenance",
                              message=f"Más de {maint_days} días sin mantenimiento (desde {start_m}).")
                    db.session.add(a); db.session.commit()
                    days = (now.date() - start_m).days
                    send_alert_email(pc.name, days, kind="maintenance")
            else:
                open_alert = Alert.query.filter_by(pc_id=pc.id, resolved=False, kind="maintenance").first()
                if open_alert:
                    open_alert.resolved = True
                    open_alert.resolved_at = now

            # --- Backup: si nunca hubo, contar desde alta ---
            last_b_obj = pc.last_backup()
            last_b = last_b_obj.date_performed.date() if last_b_obj else None
            start_b = last_b or pc_created_date(pc)                        # <-- clave
            need_b_alert = (now.date() - start_b) > timedelta(days=backup_days)

            if need_b_alert:
                existing_b = Alert.query.filter_by(pc_id=pc.id, resolved=False, kind="backup").first()
                if existing_b is None:
                    a2 = Alert(pc_id=pc.id, kind="backup",
                               message=f"Más de {backup_days} días sin backup (desde {start_b}).")
                    db.session.add(a2); db.session.commit()
                    daysb = (now.date() - start_b).days
                    send_alert_email(pc.name, daysb, kind="backup")
            else:
                open_alert_b = Alert.query.filter_by(pc_id=pc.id, resolved=False, kind="backup").first()
                if open_alert_b:
                    open_alert_b.resolved = True
                    open_alert_b.resolved_at = now

        db.session.commit()
```

**C. (Opcional, recomendado)** En `send_daily_summary()` usá el mismo criterio:

```python
def send_daily_summary():
    from .models import PC
    with app.app_context():
        vals = get_config_values()
        if not (vals.get("ALERTS_ENABLED", True) and vals.get("SUMMARY_DAILY", False)):
            return
        maint_days = vals.get("MAINT_DAYS", 7)
        backup_days = vals.get("BACKUP_DAYS", 7)
        today = datetime.now().date()

        def age_or_start(last_date, pc):
            start = last_date or pc_created_date(pc)   # <-- cuenta desde alta si no hay último
            return (today - start).days

        pcs = PC.query.order_by(PC.name.asc()).all()
        lines = ["Resumen diario de PCs en alerta:", ""]
        count = 0
        for pc in pcs:
            lm = pc.last_maintenance_date()
            lb_obj = pc.last_backup()
            lb = lb_obj.date_performed.date() if lb_obj else None
            days_m = age_or_start(lm, pc)
            days_b = age_or_start(lb, pc)
            if days_m > maint_days or days_b > backup_days:
                count += 1
                lines.append(f"- {pc.name}: mant={days_m} días, backup={days_b} días")
        if count == 0:
            lines.append("Sin alertas.")
        _send_email("[Resumen diario] Estado de PCs", "\n".join(lines))
```

---

## Verificación rápida
1) Reiniciá la app.
2) En **Admin → Configuración**, dejá **Activar envío de alertas** ON y poné umbral bajo (p.ej. 1 día).
3) **Admin → Diagnóstico**: para PCs sin mantenimiento/backup, los días deben contarse desde la **fecha de alta**.
4) En **Admin → Configuración**, tocá **Recalcular alertas ahora** y revisá **Alertas**.
5) Tocá **Enviar resumen ahora** y revisá **Logs correo** y la casilla destino.

Si necesitás, te ayudo a aplicar el parche sobre tus archivos exactos.
