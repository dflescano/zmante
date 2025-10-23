# Snippets de referencia (v3.6.3)

## utils.py — imports
from .models import ChangeLog
from datetime import datetime

## utils.py — helper
def pc_created_date(pc):
    cl = (ChangeLog.query
          .filter_by(entity="PC", entity_id=pc.id, action="create")
          .order_by(ChangeLog.created_at.asc())
          .first())
    return cl.created_at.date() if cl else datetime.now().date()

## utils.py — compute_status
def compute_status(pc, maint_days=7):
    today = datetime.now().date()
    last = pc.last_maintenance_date()
    if last is None:
        start = pc_created_date(pc)
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

## __init__.py — import
from .utils import pc_created_date

## __init__.py — check_maintenance_job
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
            last_m = pc.last_maintenance_date()
            start_m = last_m or pc_created_date(pc)
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

            last_b_obj = pc.last_backup()
            last_b = last_b_obj.date_performed.date() if last_b_obj else None
            start_b = last_b or pc_created_date(pc)
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

## __init__.py — send_daily_summary (opcional)
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
            start = last_date or pc_created_date(pc)
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
