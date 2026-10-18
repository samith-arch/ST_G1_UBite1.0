import re

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, logout_user

from .. import servicios
from ..database import db
from ..models import Producto
from ..servicios import ErrorNegocio
from . import en_linea

bp = Blueprint("cliente", __name__)

CELULAR = re.compile(r"^3\d{9}$")


@bp.before_request
def cerrar_sesion_personal():
    # si alguien del personal pasa a la parte del cliente se cierra su sesion
    if current_user.is_authenticated:
        en_linea.pop(current_user.id_usuario, None)
        logout_user()
        session.permanent = False


@bp.app_context_processor
def datos_carrito():
    carrito = session.get("carrito", {})
    return {"unidades_carrito": sum(carrito.values())}


def _carrito():
    return session.setdefault("carrito", {})


def _lineas_carrito():
    carrito = _carrito()
    lineas, total = [], 0
    for id_producto, cantidad in list(carrito.items()):
        p = db.session.get(Producto, int(id_producto))
        if p is None or not p.activo:
            carrito.pop(id_producto)
            session.modified = True
            continue
        lineas.append((p, cantidad))
        total += p.precio * cantidad
    return lineas, total


def _mio(pedido):
    return pedido is not None and pedido.codigo in session.get("mis_pedidos", [])


def _error(e, volver, texto):
    return render_template("error.html", titulo=e.titulo, mensaje=e.mensaje,
                           detalle=e.detalle, volver=volver, texto_volver=texto), 409


def _ruta_interna(url, defecto):
    return url if url.startswith("/") and not url.startswith("//") else defecto


@bp.route("/", methods=["GET", "POST"])
def inicio():
    errores, form = {}, request.form
    if request.method == "POST":
        nombre = form.get("nombre", "").strip()
        telefono = re.sub(r"\D", "", form.get("telefono", ""))
        if not nombre or len(nombre) > 60:
            errores["nombre"] = "Escribe tu nombre."
        if not CELULAR.match(telefono):
            errores["telefono"] = "Debe tener 10 dígitos y empezar por 3."
        if not errores:
            session["cliente"] = {"nombre": nombre, "telefono": telefono}
            return redirect(url_for("cliente.menu"))
    return render_template("cliente/inicio.html", errores=errores, form=form,
                           cliente=session.get("cliente"))


@bp.route("/salir")
def salir():
    session.pop("cliente", None)
    session.pop("carrito", None)
    return redirect(url_for("cliente.inicio"))


@bp.route("/menu")
def menu():
    if "cliente" not in session:
        return redirect(url_for("cliente.inicio"))
    _, total = _lineas_carrito()
    return render_template("cliente/menu.html", menu=servicios.menu_por_categoria(),
                           carrito=_carrito(), total=total)


@bp.route("/carrito/cambiar", methods=["POST"])
def carrito_cambiar():
    carrito = _carrito()
    id_producto = request.form.get("id_producto", "")
    paso = 1 if request.form.get("delta") == "1" else -1
    p = db.session.get(Producto, int(id_producto)) if id_producto.isdigit() else None
    aviso = None
    if p is not None and p.activo:
        cantidad = max(0, carrito.get(id_producto, 0) + paso)
        if cantidad > p.stock_actual:
            cantidad = p.stock_actual
            aviso = f"Solo quedan {p.stock_actual} de {p.nombre}."
        if cantidad:
            carrito[id_producto] = cantidad
        else:
            carrito.pop(id_producto, None)
        session.modified = True

    lineas, total = _lineas_carrito()
    if request.headers.get("X-Requested-With") == "fetch":
        subtotal = p.precio * carrito.get(id_producto, 0) if p else 0
        return jsonify(cantidad=carrito.get(id_producto, 0), subtotal=subtotal, total=total,
                       unidades=sum(carrito.values()), aviso=aviso)
    return redirect(_ruta_interna(request.form.get("volver", ""), url_for("cliente.menu")))


@bp.route("/carrito")
def carrito():
    if "cliente" not in session:
        return redirect(url_for("cliente.inicio"))
    lineas, total = _lineas_carrito()
    return render_template("cliente/carrito.html", lineas=lineas, total=total)


@bp.route("/pedido/confirmar", methods=["POST"])
def confirmar():
    cliente = session.get("cliente")
    if not cliente:
        return redirect(url_for("cliente.inicio"))
    items = {int(k): v for k, v in _carrito().items()}
    try:
        codigo = servicios.registrar_pedido(cliente["nombre"], cliente["telefono"], items)
    except ErrorNegocio as e:
        return _error(e, url_for("cliente.carrito"), "Revisar mi pedido")
    except Exception:
        e = ErrorNegocio("No se pudo hacer el pedido",
                         "Hubo un error y se deshizo todo: no se guardó el pedido ni se "
                         "descontó nada del inventario. Intenta de nuevo.")
        return _error(e, url_for("cliente.carrito"), "Intentar de nuevo")
    session["carrito"] = {}
    session["mis_pedidos"] = session.get("mis_pedidos", []) + [codigo]
    return redirect(url_for("cliente.seguimiento", codigo=codigo))


@bp.route("/mis-pedidos")
def mis_pedidos():
    pedidos = [servicios.buscar_pedido(c) for c in reversed(session.get("mis_pedidos", []))]
    return render_template("cliente/mis_pedidos.html", pedidos=[p for p in pedidos if p])


@bp.route("/pedido/<codigo>")
def seguimiento(codigo):
    pedido = servicios.buscar_pedido(codigo)
    if not _mio(pedido):
        return render_template("error.html", titulo="Pedido no encontrado",
                               mensaje="Solo puedes ver los pedidos que hiciste desde este celular.",
                               volver=url_for("cliente.menu"), texto_volver="Ir al menú"), 404
    if pedido.estado in ("listo", "entregado"):
        servicios.marcar_vistas(pedido)
    if pedido.estado == "listo" and not request.args.get("ver"):
        return render_template("cliente/listo.html", pedido=pedido)
    return render_template("cliente/seguimiento.html", pedido=pedido,
                           posicion=servicios.posicion_en_cola(pedido))


@bp.route("/pedido/<codigo>/estado")
def estado(codigo):
    pedido = servicios.buscar_pedido(codigo)
    if not _mio(pedido):
        return jsonify(error="no encontrado"), 404
    return jsonify(estado=pedido.estado, posicion=servicios.posicion_en_cola(pedido))


@bp.route("/pedido/<codigo>/modificar", methods=["GET", "POST"])
def modificar(codigo):
    pedido = servicios.buscar_pedido(codigo)
    if not _mio(pedido):
        return redirect(url_for("cliente.mis_pedidos"))
    if request.method == "POST":
        items = {int(k[5:]): int(v) for k, v in request.form.items()
                 if k.startswith("cant_") and v.isdigit()}
        try:
            servicios.modificar_pedido(pedido.codigo, items)
        except ErrorNegocio as e:
            return _error(e, url_for("cliente.modificar", codigo=pedido.codigo), "Volver")
        return redirect(url_for("cliente.seguimiento", codigo=pedido.codigo))
    if pedido.estado != "en_cola":
        return redirect(url_for("cliente.seguimiento", codigo=pedido.codigo))
    actuales = {d.id_producto: d.cantidad for d in pedido.detalles}
    return render_template("cliente/modificar.html", pedido=pedido, actuales=actuales,
                           menu=servicios.menu_por_categoria())


@bp.route("/pedido/<codigo>/cancelar", methods=["POST"])
def cancelar(codigo):
    pedido = servicios.buscar_pedido(codigo)
    if not _mio(pedido):
        return redirect(url_for("cliente.mis_pedidos"))
    try:
        servicios.cancelar_pedido(pedido.codigo)
    except ErrorNegocio as e:
        return _error(e, url_for("cliente.seguimiento", codigo=pedido.codigo), "Ver mi pedido")
    return redirect(url_for("cliente.seguimiento", codigo=pedido.codigo))
