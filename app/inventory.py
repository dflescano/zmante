
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from . import db
from .inventory_models import InventoryItem
from .utils_export import stream_csv, stream_xlsx, stream_pdf

bp = Blueprint("inventory", __name__, template_folder="templates")

KINDS = ("pc","monitor","router","switch","software")
STATUSES = ("activo","repuesto","retirado")

@bp.route("/", strict_slashes=False)
@bp.route("", strict_slashes=False)
@login_required
def list_items():
    kind = request.args.get("kind") or ""
    status = request.args.get("status") or ""
    q = InventoryItem.query
    if kind and kind in KINDS:
        q = q.filter(InventoryItem.kind == kind)
    if status and status in STATUSES:
        q = q.filter(InventoryItem.status == status)
    items = q.order_by(InventoryItem.created_at.desc()).all()
    return render_template("inventory_list.html", items=items, kind=kind, status=status, KINDS=KINDS, STATUSES=STATUSES)

@bp.route("/new", methods=["GET","POST"])
@login_required
def new_item():
    if request.method == "POST":
        data = {k:(request.form.get(k) or "").strip() for k in ["kind","name","brand","model","serial","asset_tag","location","assigned_to","license_key","notes"]}
        seats = request.form.get("seats") or None
        purchase_date = request.form.get("purchase_date") or None
        warranty_end = request.form.get("warranty_end") or None
        expiry_date = request.form.get("expiry_date") or None
        status = request.form.get("status") or "activo"

        it = InventoryItem(
            kind=data["kind"] if data["kind"] in KINDS else "pc",
            name=data["name"],
            brand=data["brand"] or None,
            model=data["model"] or None,
            serial=data["serial"] or None,
            asset_tag=data["asset_tag"] or None,
            location=data["location"] or None,
            assigned_to=data["assigned_to"] or None,
            license_key=data["license_key"] or None,
            seats=int(seats) if seats else None,
            purchase_date=datetime.strptime(purchase_date, "%Y-%m-%d").date() if purchase_date else None,
            warranty_end=datetime.strptime(warranty_end, "%Y-%m-%d").date() if warranty_end else None,
            expiry_date=datetime.strptime(expiry_date, "%Y-%m-%d").date() if expiry_date else None,
            status=status if status in STATUSES else "activo",
            notes=data["notes"] or None,
        )
        db.session.add(it); db.session.commit()
        flash("Ítem creado.", "success")
        return redirect(url_for("inventory.list_items"))
    return render_template("inventory_form.html", item=None, KINDS=KINDS, STATUSES=STATUSES)

@bp.route("/<int:item_id>")
@login_required
def view_item(item_id):
    it = InventoryItem.query.get_or_404(item_id)
    return render_template("inventory_detail.html", item=it)

@bp.route("/<int:item_id>/edit", methods=["GET","POST"])
@login_required
def edit_item(item_id):
    it = InventoryItem.query.get_or_404(item_id)
    if request.method == "POST":
        it.kind = (request.form.get("kind") or it.kind)
        it.name = (request.form.get("name") or it.name)
        it.brand = (request.form.get("brand") or None)
        it.model = (request.form.get("model") or None)
        it.serial = (request.form.get("serial") or None)
        it.asset_tag = (request.form.get("asset_tag") or None)
        it.location = (request.form.get("location") or None)
        it.assigned_to = (request.form.get("assigned_to") or None)
        it.license_key = (request.form.get("license_key") or None)
        seats = request.form.get("seats") or None
        it.seats = int(seats) if seats else None
        for fld in ("purchase_date","warranty_end","expiry_date"):
            val = request.form.get(fld)
            setattr(it, fld, datetime.strptime(val, "%Y-%m-%d").date() if val else None)
        st = request.form.get("status")
        it.status = st if st in ("activo","repuesto","retirado") else it.status
        it.notes = (request.form.get("notes") or None)
        db.session.commit()
        flash("Ítem actualizado.", "success")
        return redirect(url_for("inventory.view_item", item_id=it.id))
    return render_template("inventory_form.html", item=it, KINDS=KINDS, STATUSES=STATUSES)

@bp.route("/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id):
    if not getattr(current_user, "role", "") == "admin":
        abort(403)
    it = InventoryItem.query.get_or_404(item_id)
    db.session.delete(it)
    db.session.commit()
    flash("Ítem eliminado.", "success")
    return redirect(url_for("inventory.list_items"))

@bp.route("/export.csv")
@login_required
def export_csv():
    q = InventoryItem.query.order_by(InventoryItem.created_at.desc()).all()
    headers = ["id","kind","name","brand","model","serial","asset_tag","location","assigned_to","license_key","seats","purchase_date","warranty_end","expiry_date","status","notes","created_at","updated_at"]
    rows = [[i.id,i.kind,i.name,i.brand,i.model,i.serial,i.asset_tag,i.location,i.assigned_to,i.license_key,i.seats,i.purchase_date,i.warranty_end,i.expiry_date,i.status,i.notes,i.created_at,i.updated_at] for i in q]
    return stream_csv("inventory.csv", headers, rows)

@bp.route("/export.xlsx")
@login_required
def export_xlsx():
    q = InventoryItem.query.order_by(InventoryItem.created_at.desc()).all()
    headers = ["id","kind","name","brand","model","serial","asset_tag","location","assigned_to","license_key","seats","purchase_date","warranty_end","expiry_date","status","notes","created_at","updated_at"]
    rows = [[i.id,i.kind,i.name,i.brand,i.model,i.serial,i.asset_tag,i.location,i.assigned_to,i.license_key,i.seats,i.purchase_date,i.warranty_end,i.expiry_date,i.status,i.notes,i.created_at,i.updated_at] for i in q]
    return stream_xlsx("inventory.xlsx", headers, rows)

@bp.route("/export.pdf")
@login_required
def export_pdf():
    q = InventoryItem.query.order_by(InventoryItem.created_at.desc()).all()
    headers = ["ID","Tipo","Nombre","Marca","Modelo","Serie","Tag","Ubicación","Asignado","Estado"]
    rows = [[i.id,i.kind,i.name,i.brand,i.model,i.serial,i.asset_tag,i.location,i.assigned_to,i.status] for i in q]
    return stream_pdf("inventory.pdf", "Inventario", headers, rows)
