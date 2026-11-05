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
    filtros = {"buscar": request.args.get("buscar", "")[:60],
               "categoria": request.args.get("categoria", ""),
               "estado": request.args.get("estado", "")}
    todos = gestion.inventario()
    productos = gestion.inventario(**filtros) if any(filtros.values()) else todos
    bajos = [p for p in todos if p.activo and p.stock_actual <= p.stock_minimo]
    return render_template("inventario/lista.html", productos=productos, bajos=bajos, total=len(todos),
                           filtros=filtros, estado=gestion.estado_producto,
                           categorias=Categoria.query.order_by(Categoria.nombre).all(),
                           tope=max([p.stock_actual for p in todos] + [1]))


@bp.route("/editar")
@rol_requerido("administrador")
def editar():
    elegido = request.args.get("id", type=int)
    if elegido and db.session.get(Producto, elegido):
        return redirect(url_for("inventario.producto", id_producto=elegido))
    return render_template("inventario/elegir.html", productos=gestion.inventario())


@bp.route("/eliminar", methods=["GET", "POST"])
@rol_requerido("administrador")
def eliminar():
    if request.method == "POST":
        id_producto = request.form.get("id_producto", "")
        try:
            nombre = gestion.eliminar_producto(int(id_producto) if id_producto.isdigit() else 0)
            flash(f"{nombre} se eliminó del inventario.")
            return redirect(url_for("inventario.lista"))
        except ErrorNegocio as e:
            flash(f"{e.titulo}: {e.mensaje}", "error")
            return redirect(url_for("inventario.eliminar", id=id_producto))
    elegido = request.args.get("id", type=int)
    p = db.session.get(Producto, elegido) if elegido else None
    return render_template("inventario/eliminar.html", productos=gestion.inventario(), p=p,
                           ventas=gestion.ventas_producto(p.id_producto) if p else 0)


@bp.route("/entrada", methods=["GET", "POST"])
@rol_requerido("cajero", "administrador")
def entrada():
    if request.method == "POST":
        try:
            id_producto = request.form.get("id_producto", "")
            nombre, stock = gestion.entrada_stock(int(id_producto) if id_producto.isdigit() else 0,
                                                  request.form.get("cantidad"))
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
