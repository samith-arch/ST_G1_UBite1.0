import csv
import io
from datetime import date, datetime, timedelta

import qrcode
import qrcode.image.svg
from flask import (Blueprint, Response, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user
from markupsafe import Markup

from .. import gestion
from ..models import Usuario
from ..servicios import ErrorNegocio
from . import en_linea, rol_requerido

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _fecha():
    try:
        return date.fromisoformat(request.args.get("fecha", ""))
    except ValueError:
        return gestion.hoy()


@bp.route("/reporte")
@rol_requerido("administrador")
def reporte():
    fecha = _fecha()
    return render_template("admin/reporte.html", r=gestion.reporte(fecha), fecha=fecha,
                           hoy=gestion.hoy(), ayer=fecha - timedelta(days=1),
                           manana=fecha + timedelta(days=1))


@bp.route("/reporte.csv")
@rol_requerido("administrador")
def exportar():
    fecha = _fecha()
    salida = io.StringIO()
    w = csv.writer(salida, delimiter=";")
    w.writerow(["codigo", "hora", "cliente", "origen", "estado", "pago", "total"])
    for p in gestion.reporte(fecha)["lista"]:
        pago = next((x for x in p.pagos if x.estado == "aprobado"), None)
        w.writerow([p.codigo, p.fecha_hora.strftime("%H:%M"), p.cliente.nombre, p.origen,
                    p.estado, pago.metodo if pago else "pendiente", int(p.total)])
    # el BOM es para que Excel abra bien las tildes
    return Response("﻿" + salida.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=reporte_{fecha}.csv"})


@bp.route("/clientes")
@rol_requerido("administrador")
def clientes():
    buscar = request.args.get("buscar", "").strip()
    filas = gestion.clientes(buscar)
    return render_template("admin/clientes.html", filas=filas, buscar=buscar,
                           activos=sum(1 for f in filas if f["activo"]))


@bp.route("/usuarios", methods=["GET", "POST"])
@rol_requerido("administrador")
def usuarios():
    if request.method == "POST":
        accion = request.form.get("accion")
        try:
            if accion == "crear":
                gestion.crear_usuario(request.form.get("nombre", ""), request.form.get("username", ""),
                                      request.form.get("rol", ""), request.form.get("clave", ""))
                flash("Usuario creado.")
            elif accion == "activo":
                nombre, activo = gestion.cambiar_activo(int(request.form["id_usuario"]), current_user)
                if not activo:
                    en_linea.pop(int(request.form["id_usuario"]), None)
                flash(f"{nombre} quedó {'activo' if activo else 'inactivo'}.")
            elif accion == "clave":
                nombre = gestion.cambiar_clave(int(request.form["id_usuario"]), request.form.get("clave", ""))
                flash(f"Se cambió la contraseña de {nombre}.")
        except ErrorNegocio as e:
            flash(f"{e.titulo}: {e.mensaje}", "error")
        return redirect(url_for("admin.usuarios"))

    limite = datetime.now() - timedelta(minutes=15)
    conectados = {i for i, t in en_linea.items() if t >= limite}
    lista = Usuario.query.order_by(Usuario.activo.desc(), Usuario.nombre).all()
    return render_template("admin/usuarios.html", usuarios=lista, conectados=conectados)


@bp.route("/qr")
@rol_requerido("administrador")
def qr():
    direccion = request.args.get("url") or request.host_url
    imagen = qrcode.make(direccion, image_factory=qrcode.image.svg.SvgPathImage, box_size=12, border=2)
    svg = imagen.to_string(encoding="unicode")
    return render_template("admin/qr.html", direccion=direccion, svg=Markup(svg))
