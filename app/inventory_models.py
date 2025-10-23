
from datetime import datetime
from . import db

class InventoryItem(db.Model):
    __tablename__ = "inventory_item"
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(32), nullable=False, index=True)   # pc, monitor, router, switch, software
    name = db.Column(db.String(120), nullable=False)
    brand = db.Column(db.String(120))
    model = db.Column(db.String(120))
    serial = db.Column(db.String(120), index=True)
    asset_tag = db.Column(db.String(120), index=True)
    location = db.Column(db.String(120))
    assigned_to = db.Column(db.String(120))
    license_key = db.Column(db.String(255))
    seats = db.Column(db.Integer)
    expiry_date = db.Column(db.Date)
    purchase_date = db.Column(db.Date)
    warranty_end = db.Column(db.Date)
    status = db.Column(db.String(32), default="activo")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
