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


@bp.route("/producto/<int:id_producto>/eliminar", methods=["POST"])
@rol_requerido("administrador")
def eliminar(id_producto):
    try:
        flash(f"{gestion.eliminar_producto(id_producto)} se eliminó del inventario.")
    except ErrorNegocio as e:
        flash(f"{e.titulo}: {e.mensaje}", "error")
    return redirect(url_for("inventario.lista"))


@bp.route("/producto/<int:id_producto>/activo", methods=["POST"])
@rol_requerido("administrador")
def activo(id_producto):
    try:
        nombre, activo = gestion.cambiar_activo_producto(id_producto)
        flash(f"{nombre} {'vuelve a mostrarse' if activo else 'ya no se muestra'} en el menú.")
    except ErrorNegocio as e:
        flash(f"{e.titulo}: {e.mensaje}", "error")
    return redirect(request.referrer if request.referrer and request.host in request.referrer
                    else url_for("inventario.lista"))


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
