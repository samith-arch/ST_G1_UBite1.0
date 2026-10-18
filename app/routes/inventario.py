from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from .. import gestion
from ..database import db
from ..models import Categoria, Producto
from ..servicios import ErrorNegocio
from . import rol_requerido

bp = Blueprint("inventario", __name__, url_prefix="/inventario")


@bp.route("/")
@rol_requerido("cajero", "administrador")
def lista():
    productos = gestion.inventario()
    bajos = [p for p in productos if p.activo and p.stock_actual <= p.stock_minimo]
    return render_template("inventario/lista.html", productos=productos, bajos=bajos,
                           estado=gestion.estado_producto,
                           categorias=len({p.id_categoria for p in productos}),
                           tope=max([p.stock_actual for p in productos] + [1]))


@bp.route("/entrada", methods=["GET", "POST"])
@rol_requerido("cajero", "administrador")
def entrada():
    if request.method == "POST":
        try:
            nombre, stock = gestion.entrada_stock(int(request.form.get("id_producto", 0)),
                                                  int(request.form.get("cantidad") or 0))
            flash(f"Entrada registrada: {nombre} queda con {stock} unidades.")
            return redirect(url_for("inventario.lista"))
        except ErrorNegocio as e:
            flash(f"{e.titulo}: {e.mensaje}", "error")
        except ValueError:
            flash("Escribe una cantidad válida.", "error")
    elegido = request.args.get("producto", type=int)
    return render_template("inventario/entrada.html", productos=gestion.inventario(), elegido=elegido)


@bp.route("/producto/nuevo", methods=["GET", "POST"])
@bp.route("/producto/<int:id_producto>", methods=["GET", "POST"])
@rol_requerido("administrador")
def producto(id_producto=None):
    p = db.session.get(Producto, id_producto) if id_producto else None
    if id_producto and p is None:
        return redirect(url_for("inventario.lista"))
    datos = request.form if request.method == "POST" else None
    if datos is not None:
        try:
            nombre = gestion.guardar_producto(datos, id_producto)
            flash(f"{nombre} guardado.")
            return redirect(url_for("inventario.lista"))
        except ErrorNegocio as e:
            flash(f"{e.titulo}: {e.mensaje}", "error")
    return render_template("inventario/producto.html", p=p, datos=datos,
                           categorias=Categoria.query.order_by(Categoria.nombre).all(),
                           es_admin=current_user.rol == "administrador")
