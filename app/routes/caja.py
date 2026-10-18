import re

from flask import (Blueprint, current_app, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user

from .. import avisos, servicios
from ..database import BaseOcupada
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
            codigo, _ = servicios.cambiar_estado(id_pedido, "en_preparacion", current_user)
            flash(f"{codigo} pasó a preparación.")
        elif accion == "listo":
            codigo, aviso = servicios.cambiar_estado(id_pedido, "listo", current_user)
            if aviso:
                url = url_for("cliente.seguimiento", codigo=codigo, _external=True)
                avisos.enviar_en_segundo_plano(current_app._get_current_object(), aviso, url)
                flash(f"{codigo} está listo, se envió el aviso al celular del cliente.")
            else:
                flash(f"{codigo} está listo. El cliente no activó los avisos, lo verá en su página.")
        elif accion == "entregar":
            cobrar = request.form.get("cobrar") == "1"
            codigo = servicios.entregar_o_rechazar(id_pedido, current_user, cobrar)
            flash(f"{codigo} {'cobrado y ' if cobrar else ''}entregado.")
        elif accion == "cancelar":
            codigo = request.form.get("codigo", "")
            servicios.cancelar_pedido(codigo, usuario=current_user)
            flash(f"{codigo} cancelado y el stock devuelto.")
    except ErrorNegocio as e:
        if e.filas:
            # pantalla E5: se muestra completa porque hay que entender que paso
            return render_template("caja/rechazo.html", e=e), 409
        flash(f"{e.titulo}: {e.mensaje}", "error")
    except BaseOcupada:
        flash("La base de datos está ocupada con otros pedidos. No se guardó nada, intenta otra vez.", "error")
    except Exception:
        current_app.logger.exception("fallo en la cola del cajero")
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
        detalle = " · ".join(f"{a}: {b}" for a, b in e.filas[:-3]) if e.faltantes else e.mensaje
        flash(f"{e.titulo}. {detalle}. No se guardó nada.", "error")
        return render_template("caja/presencial.html", menu=menu, form=request.form, codigo=codigo)
    except BaseOcupada:
        flash("La base de datos está ocupada con otros pedidos. No se guardó nada, intenta otra vez.", "error")
        return render_template("caja/presencial.html", menu=menu, form=request.form, codigo=codigo)
    except Exception:
        current_app.logger.exception("fallo registrando un pedido presencial")
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
