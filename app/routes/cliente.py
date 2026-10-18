"""Vistas del cliente: entrada por QR, menú, carrito, pedido y seguimiento."""
import re

from flask import (Blueprint, jsonify, redirect, render_template, request,
                   session, url_for)

from ..database import db
from ..models import Producto
from .. import servicios
from ..servicios import ErrorNegocio

bp = Blueprint("cliente", __name__)

TELEFONO = re.compile(r"^3\d{9}$")


# ---------------------------------------------------------------------------
# Utilidades de sesión
# ---------------------------------------------------------------------------
def _carrito():
    return session.setdefault("carrito", {})


def _resumen_carrito():
    carrito = _carrito()
    lineas, total, unidades = [], 0, 0
    for id_producto, cantidad in list(carrito.items()):
        producto = db.session.get(Producto, int(id_producto))
        if producto is None or not producto.activo:
            carrito.pop(id_producto)
            session.modified = True
            continue
        lineas.append((producto, cantidad))
        total += producto.precio * cantidad
        unidades += cantidad
    return lineas, total, unidades


def _es_mio(codigo):
    return codigo in session.get("mis_pedidos", [])


def _error(e, volver=None, texto_volver="Volver"):
    return render_template("error.html", titulo=e.titulo, mensaje=e.mensaje,
                           detalle=e.detalle, volver=volver, texto_volver=texto_volver), 409


# ---------------------------------------------------------------------------
# Entrada por QR y datos del cliente
# ---------------------------------------------------------------------------
@bp.route("/", methods=["GET", "POST"])
def inicio():
    errores = {}
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        telefono = re.sub(r"\D", "", request.form.get("telefono", ""))
        if not nombre or len(nombre) > 60:
            errores["nombre"] = "Escribe tu nombre (máximo 60 caracteres)."
        if not TELEFONO.match(telefono):
            errores["telefono"] = "Escribe un celular de 10 dígitos que empiece por 3."
        if not errores and request.form.get("acepta") != "si":
            errores["acepta"] = "Necesitamos tu autorización para usar estos datos."
        if not errores:
            session["cliente"] = {"nombre": nombre, "telefono": telefono}
            return redirect(url_for("cliente.menu"))
    return render_template("cliente/inicio.html", errores=errores,
                           cliente=session.get("cliente"), form=request.form)


@bp.route("/salir")
def salir():
    session.pop("cliente", None)
    session.pop("carrito", None)
    return redirect(url_for("cliente.inicio"))


# ---------------------------------------------------------------------------
# Menú y carrito
# ---------------------------------------------------------------------------
@bp.route("/menu")
def menu():
    if "cliente" not in session:
        return redirect(url_for("cliente.inicio"))
    _, total, unidades = _resumen_carrito()
    return render_template("cliente/menu.html", menu=servicios.menu_por_categoria(),
                           carrito=_carrito(), total=total, unidades=unidades)


@bp.route("/carrito/cambiar", methods=["POST"])
def carrito_cambiar():
    """Suma o resta una unidad. Responde JSON si lo pide el JavaScript del menú
    y redirige al menú si el navegador no tiene JavaScript."""
    carrito = _carrito()
    id_producto = request.form.get("id_producto", "")
    delta = 1 if request.form.get("delta") == "1" else -1
    producto = db.session.get(Producto, int(id_producto)) if id_producto.isdigit() else None
    aviso = None
    if producto is not None and producto.activo:
        actual = carrito.get(id_producto, 0)
        nueva = max(0, actual + delta)
        if nueva > producto.stock_actual:
            nueva = producto.stock_actual
            aviso = f"Solo quedan {producto.stock_actual} de {producto.nombre}."
        if nueva:
            carrito[id_producto] = nueva
        else:
            carrito.pop(id_producto, None)
        session.modified = True
    _, total, unidades = _resumen_carrito()
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify(cantidad=carrito.get(id_producto, 0), total=total,
                       unidades=unidades, aviso=aviso)
    volver = request.form.get("volver", "")
    if not volver.startswith("/") or volver.startswith("//"):
        volver = url_for("cliente.menu")
    return redirect(volver)


@bp.route("/carrito")
def carrito():
    if "cliente" not in session:
        return redirect(url_for("cliente.inicio"))
    lineas, total, unidades = _resumen_carrito()
    return render_template("cliente/carrito.html", lineas=lineas, total=total, unidades=unidades)


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
        e = ErrorNegocio("No pudimos registrar tu pedido",
                         "Ocurrió un error y se deshizo la operación completa: no se guardó el "
                         "pedido ni se descontó nada del inventario. Intenta de nuevo.")
        return _error(e, url_for("cliente.carrito"), "Intentar de nuevo")
    session["carrito"] = {}
    session["mis_pedidos"] = session.get("mis_pedidos", []) + [codigo]
    return redirect(url_for("cliente.seguimiento", codigo=codigo))


# ---------------------------------------------------------------------------
# Seguimiento, modificación y cancelación
# ---------------------------------------------------------------------------
@bp.route("/mis-pedidos")
def mis_pedidos():
    codigos = session.get("mis_pedidos", [])
    pedidos = [p for p in (servicios.buscar_pedido(c) for c in reversed(codigos)) if p]
    return render_template("cliente/mis_pedidos.html", pedidos=pedidos)


@bp.route("/pedido/<codigo>")
def seguimiento(codigo):
    pedido = servicios.buscar_pedido(codigo)
    if pedido is None or not _es_mio(pedido.codigo):
        return render_template("error.html", titulo="Pedido no encontrado",
                               mensaje="Solo puedes ver los pedidos que hiciste desde este celular.",
                               volver=url_for("cliente.menu"), texto_volver="Ir al menú"), 404
    if pedido.estado in ("listo", "entregado"):
        servicios.marcar_notificaciones_vistas(pedido)
    return render_template("cliente/seguimiento.html", pedido=pedido,
                           posicion=servicios.posicion_en_cola(pedido))


@bp.route("/pedido/<codigo>/estado")
def estado(codigo):
    """Lo consulta la página de seguimiento cada pocos segundos."""
    pedido = servicios.buscar_pedido(codigo)
    if pedido is None or not _es_mio(pedido.codigo):
        return jsonify(error="no encontrado"), 404
    return jsonify(estado=pedido.estado, posicion=servicios.posicion_en_cola(pedido))


@bp.route("/pedido/<codigo>/modificar", methods=["GET", "POST"])
def modificar(codigo):
    pedido = servicios.buscar_pedido(codigo)
    if pedido is None or not _es_mio(pedido.codigo):
        return redirect(url_for("cliente.mis_pedidos"))
    if request.method == "POST":
        items = {}
        for clave, valor in request.form.items():
            if clave.startswith("cant_") and valor.isdigit():
                items[int(clave[5:])] = int(valor)
        try:
            servicios.modificar_pedido(pedido.codigo, items)
        except ErrorNegocio as e:
            return _error(e, url_for("cliente.modificar", codigo=pedido.codigo), "Volver a intentar")
        return redirect(url_for("cliente.seguimiento", codigo=pedido.codigo))
    if pedido.estado != "en_cola":
        return redirect(url_for("cliente.seguimiento", codigo=pedido.codigo))
    actuales = {d.id_producto: d.cantidad for d in pedido.detalles}
    return render_template("cliente/modificar.html", pedido=pedido, actuales=actuales,
                           menu=servicios.menu_por_categoria())


@bp.route("/pedido/<codigo>/cancelar", methods=["POST"])
def cancelar(codigo):
    pedido = servicios.buscar_pedido(codigo)
    if pedido is None or not _es_mio(pedido.codigo):
        return redirect(url_for("cliente.mis_pedidos"))
    try:
        servicios.cancelar_pedido(pedido.codigo)
    except ErrorNegocio as e:
        return _error(e, url_for("cliente.seguimiento", codigo=pedido.codigo), "Ver mi pedido")
    return redirect(url_for("cliente.seguimiento", codigo=pedido.codigo))
