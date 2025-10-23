# app/time_helpers.py
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import current_app

def app_tz():
    return current_app.config.get("APP_TZ", ZoneInfo("America/Argentina/Buenos_Aires"))

def now_local():
    return datetime.now(app_tz())

def to_local(dt):
    if dt is None:
        return None
    tz = app_tz()
    naive_as = (current_app.config.get("NAIVE_AS") or "UTC").upper()
    if dt.tzinfo is None:
        # << clave: tratamos ingenuos como UTC por defecto >>
        if naive_as == "UTC":
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        else:
            dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz)
