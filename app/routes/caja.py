"""Panel del cajero: cola de pedidos, cambios de estado, cobro en caja y
registro de pedidos presenciales."""
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
    columnas = {e: [p for p in pedidos if p.estado == e] for e in servicios.ESTADOS_ACTIVOS}
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
            flash(f"{codigo} está listo; se avisó al cliente.")
        elif accion == "entregar":
            codigo = servicios.entregar_pedido(id_pedido, current_user)
            flash(f"{codigo} entregado.")
        elif accion == "cancelar":
            codigo = request.form.get("codigo", "")
            servicios.cancelar_pedido(codigo, usuario=current_user)
            flash(f"{codigo} cancelado; el stock se devolvió.")
    except ErrorNegocio as e:
        flash(f"{e.titulo}: {e.mensaje}", "error")
    except Exception:
        flash("No se pudo completar la operación; se deshizo sin guardar cambios.", "error")
    return redirect(url_for("caja.cola"))


@bp.route("/presencial", methods=["GET", "POST"])
@rol_requerido(*PERSONAL)
def presencial():
    menu = servicios.menu_por_categoria()
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        telefono = re.sub(r"\D", "", request.form.get("telefono", ""))
        items = {}
        for clave, valor in request.form.items():
            if clave.startswith("cant_") and valor.isdigit() and int(valor) > 0:
                items[int(clave[5:])] = int(valor)
        if not nombre or not re.match(r"^3\d{9}$", telefono):
            flash("Escribe el nombre del cliente y un celular de 10 dígitos que empiece por 3.", "error")
            return render_template("caja/presencial.html", menu=menu, form=request.form)
        try:
            codigo = servicios.registrar_pedido(nombre, telefono, items, origen="presencial",
                                                usuario=current_user)
        except ErrorNegocio as e:
            flash(f"{e.titulo}: {' · '.join(e.detalle) or e.mensaje}", "error")
            return render_template("caja/presencial.html", menu=menu, form=request.form)
        except Exception:
            flash("No se pudo registrar el pedido; se deshizo sin guardar cambios.", "error")
            return render_template("caja/presencial.html", menu=menu, form=request.form)
        flash(f"Pedido {codigo} registrado y enviado a la cola.")
        return redirect(url_for("caja.cola"))
    return render_template("caja/presencial.html", menu=menu, form={})


@bp.route("/historial")
@rol_requerido(*PERSONAL)
def historial():
    pedidos = servicios.pedidos_del_dia()
    entregados = [p for p in pedidos if p.estado == "entregado"]
    return render_template("caja/historial.html", pedidos=pedidos,
                           vendido=sum(p.total for p in entregados), entregados=len(entregados))
