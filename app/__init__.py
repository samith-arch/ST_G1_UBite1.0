import os
import secrets

from flask import Flask, abort, render_template, request, session
from flask_login import LoginManager

from .database import db, get_database_uri

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Inicia sesión para entrar al panel."


def pesos(valor):
    """3500 -> '3.500'"""
    return f"{valor:,.0f}".replace(",", ".")


ESTADOS = {
    "en_cola": "En cola",
    "en_preparacion": "En preparación",
    "listo": "Listo para recoger",
    "entregado": "Entregado",
    "cancelado": "Cancelado",
}


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = get_database_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # En producción la clave se define como variable de entorno
    app.config["SECRET_KEY"] = os.environ.get("UBITE_SECRET_KEY", "clave-solo-para-desarrollo-local")

    db.init_app(app)
    login_manager.init_app(app)

    app.jinja_env.filters["pesos"] = pesos
    app.jinja_env.globals["ESTADOS"] = ESTADOS

    with app.app_context():
        from . import models  # noqa: F401 - registra los modelos en SQLAlchemy

    from .routes.auth import bp as auth_bp
    from .routes.caja import bp as caja_bp
    from .routes.cliente import bp as cliente_bp
    app.register_blueprint(cliente_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(caja_bp)

    # Protección CSRF sencilla: cada formulario lleva un token que debe
    # coincidir con el guardado en la sesión
    def csrf_token():
        if "_csrf" not in session:
            session["_csrf"] = secrets.token_urlsafe(32)
        return session["_csrf"]

    app.jinja_env.globals["csrf_token"] = csrf_token
    @app.before_request
    def validar_csrf():
        if request.method == "POST":
            enviado = request.form.get("_csrf") or request.headers.get("X-CSRF-Token")
            if not enviado or enviado != session.get("_csrf"):
                abort(400)
    @app.errorhandler(400)
    def solicitud_invalida(_e):
        return render_template("error.html", titulo="La página se venció",
                               mensaje="Recarga la página e intenta de nuevo."), 400
    @app.errorhandler(403)
    def prohibido(_e):
        return render_template("error.html", titulo="Sin permiso",
                               mensaje="Tu usuario no tiene permiso para entrar aquí."), 403
    @app.errorhandler(404)
    def no_encontrado(_e):
        return render_template("error.html", titulo="Página no encontrada",
                               mensaje="La dirección que abriste no existe."), 404
    return app
@login_manager.user_loader
def cargar_usuario(id_usuario):
    from .models import Usuario
    return db.session.get(Usuario, int(id_usuario))
