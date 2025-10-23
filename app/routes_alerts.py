from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from .models import Alert
from . import db

bp_alerts = Blueprint("alerts_bp", __name__)

@bp_alerts.route("/alerts")
@login_required
def alerts_list():
    alerts = Alert.query.order_by(Alert.created_at.desc()).all()
    return render_template("alerts.html", alerts=alerts)

@bp_alerts.route("/alerts/<int:alert_id>/resolve", methods=["POST"])
@login_required
def alerts_resolve(alert_id):
    a = Alert.query.get_or_404(alert_id)
    if not a.resolved:
        a.resolved = True
        from datetime import datetime
        a.resolved_at = datetime.now()
        db.session.commit()
        flash("Alerta resuelta.", "success")
    return redirect(url_for("alerts_bp.alerts_list"))
