import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from .. import servicios
from ..servicios import ErrorNegocio
from . import rol_requerido

bp = Blueprint("caja", __name__, url_prefix="/caja")

PERSONAL = ("cajero", "administrador")


@bp.route("/")
@rol_requerido(*PERSONAL)
def cola():
    pedidos = servicios.cola_activa()
    columnas = {e: [p for p in pedidos if p.estado == e] for e in servicios.ACTIVOS}
    buscar = request.args.get("buscar", "").strip()
    encontrado = servicios.buscar_pedido(buscar) if buscar else None
    return render_template("caja/cola.html", columnas=columnas, buscar=buscar,
                           encontrado=encontrado)


@bp.route("/pedido/<int:id_pedido>/estado", methods=["POST"])
@rol_requerido(*PERSONAL)
def cambiar_estado(id_pedido):
    accion = request.form.get("accion")
    try:
        if accion == "preparar":
            codigo = servicios.cambiar_estado(id_pedido, "en_preparacion", current_user)
            flash(f"{codigo} pasó a preparación.")
        elif accion == "listo":
            codigo = servicios.cambiar_estado(id_pedido, "listo", current_user)
            flash(f"{codigo} está listo, ya se le avisó al cliente.")
        elif accion == "entregar":
            codigo = servicios.entregar_pedido(id_pedido, current_user)
            flash(f"{codigo} entregado.")
        elif accion == "cancelar":
            codigo = request.form.get("codigo", "")
            servicios.cancelar_pedido(codigo, usuario=current_user)
            flash(f"{codigo} cancelado y el stock devuelto.")
    except ErrorNegocio as e:
        flash(f"{e.titulo}: {e.mensaje}", "error")
    except Exception:
        flash("No se pudo hacer la operación, no se guardó ningún cambio.", "error")
    return redirect(url_for("caja.cola"))


@bp.route("/presencial", methods=["GET", "POST"])
@rol_requerido(*PERSONAL)
def presencial():
    menu = servicios.menu_por_categoria()
    codigo = servicios.siguiente_codigo("presencial")
    if request.method == "GET":
        return render_template("caja/presencial.html", menu=menu, form={}, codigo=codigo)

    nombre = request.form.get("nombre", "").strip()
    telefono = re.sub(r"\D", "", request.form.get("telefono", ""))
    items = {int(k[5:]): int(v) for k, v in request.form.items()
             if k.startswith("cant_") and v.isdigit() and int(v) > 0}

    error = None
    if not nombre:
        error = "Escribe el nombre del cliente."
    elif telefono and not re.match(r"^3\d{9}$", telefono):
        error = "El celular debe tener 10 dígitos y empezar por 3."
    if error:
        flash(error, "error")
        return render_template("caja/presencial.html", menu=menu, form=request.form, codigo=codigo)

    try:
        codigo = servicios.registrar_pedido(nombre, telefono, items, origen="presencial",
                                            usuario=current_user)
    except ErrorNegocio as e:
        flash(f"{e.titulo}: {' · '.join(e.detalle) or e.mensaje}", "error")
        return render_template("caja/presencial.html", menu=menu, form=request.form, codigo=codigo)
    except Exception:
        flash("No se pudo registrar el pedido, no se guardó ningún cambio.", "error")
        return render_template("caja/presencial.html", menu=menu, form=request.form, codigo=codigo)
    flash(f"Pedido {codigo} cobrado y enviado a preparación.")
    return redirect(url_for("caja.cola"))


@bp.route("/historial")
@rol_requerido(*PERSONAL)
def historial():
    pedidos = servicios.pedidos_del_dia()
    entregados = [p for p in pedidos if p.estado == "entregado"]
    return render_template("caja/historial.html", pedidos=pedidos,
                           vendido=sum(p.total for p in entregados), entregados=len(entregados))
