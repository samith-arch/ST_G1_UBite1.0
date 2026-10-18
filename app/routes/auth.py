from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash

from ..models import Usuario

bp = Blueprint("auth", __name__, url_prefix="/personal")


def _inicio_segun_rol(usuario):
    # El panel del administrador se agrega en la siguiente etapa;
    # por ahora los dos roles entran a la cola de pedidos
    return url_for("caja.cola")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_inicio_segun_rol(current_user))
    if request.method == "POST":
        usuario = Usuario.query.filter_by(username=request.form.get("usuario", "").strip()).first()
        if usuario and usuario.activo and check_password_hash(usuario.password_hash,
                                                              request.form.get("contrasena", "")):
            login_user(usuario)
            destino = request.args.get("next", "")
            # Solo se aceptan rutas internas, para no redirigir a otro sitio
            if not destino.startswith("/") or destino.startswith("//"):
                destino = _inicio_segun_rol(usuario)
            return redirect(destino)
        flash("Usuario o contraseña incorrectos.")
    return render_template("auth/login.html")


@bp.route("/salir")
def salir():
    logout_user()
    return redirect(url_for("auth.login"))
