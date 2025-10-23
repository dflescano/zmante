from app import create_app

app = create_app()
if app is None:
    raise RuntimeError("create_app() devolvió None. Revisá el return app al final de app/__init__.py")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
