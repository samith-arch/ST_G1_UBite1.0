from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash

from ..models import Usuario
from . import en_linea

bp = Blueprint("auth", __name__, url_prefix="/personal")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        # cada vez que se abre el login se pide usuario y contraseña de nuevo
        _cerrar()
        return render_template("auth/login.html")

    usuario = Usuario.query.filter_by(username=request.form.get("usuario", "").strip().lower()).first()
    clave = request.form.get("contrasena", "")
    if not usuario or not usuario.activo or not check_password_hash(usuario.password_hash, clave):
        flash("Usuario o contraseña incorrectos.")
        return render_template("auth/login.html"), 401

    session.permanent = True
    login_user(usuario)
    if usuario.rol == "administrador":
        return redirect(url_for("admin.reporte"))
    return redirect(url_for("caja.cola"))


def _cerrar():
    if current_user.is_authenticated:
        en_linea.pop(current_user.id_usuario, None)
    logout_user()
    session.permanent = False


@bp.route("/salir")
def salir():
    _cerrar()
    return redirect(url_for("auth.login"))
