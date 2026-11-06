import csv
import io
from datetime import date, datetime, timedelta

import qrcode
import qrcode.image.svg
from flask import (Blueprint, Response, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user
from markupsafe import Markup

from .. import alertas_ia, gestion
from ..database import db
from ..models import Usuario
from ..servicios import ErrorNegocio
from . import en_linea, rol_requerido

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _filtro_reporte():
    hoy = gestion.hoy()
    try:
        fecha = date.fromisoformat(request.args.get("fecha", ""))
    except ValueError:
        fecha = hoy
    periodo = request.args.get("periodo", "dia")
    if periodo not in gestion.PERIODOS:
        periodo = "dia"
    # no hay reportes del futuro
    return min(fecha, hoy), periodo


@bp.route("/reporte")
@rol_requerido("administrador")
def reporte():
    fecha, periodo = _filtro_reporte()
    r = gestion.reporte(fecha, periodo)
    hoy = gestion.hoy()
    siguiente = r["hasta"] + timedelta(days=1)
    return render_template("admin/reporte.html", r=r, fecha=fecha, periodo=periodo, hoy=hoy,
                           anterior=r["desde"] - timedelta(days=1),
                           siguiente=siguiente if siguiente <= hoy else None)


@bp.route("/reporte.csv")
@rol_requerido("administrador")
def exportar():
    fecha, periodo = _filtro_reporte()
    r = gestion.reporte(fecha, periodo)
    salida = io.StringIO()
    w = csv.writer(salida, delimiter=";")
    w.writerow(["codigo", "fecha", "hora", "cliente", "origen", "estado", "pago", "total"])
    for p in r["lista"]:
        pago = next((x for x in p.pagos if x.estado == "aprobado"), None)
        w.writerow([p.codigo, p.fecha_hora.strftime("%Y-%m-%d"), p.fecha_hora.strftime("%H:%M"),
                    p.cliente.nombre, p.origen, p.estado, pago.metodo if pago else "pendiente", int(p.total)])
    nombre = f"reporte_{r['desde']}" + (f"_a_{r['hasta']}" if r["desde"] != r["hasta"] else "")
    # el BOM es para que Excel abra bien las tildes
    return Response("﻿" + salida.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={nombre}.csv"})


@bp.route("/alertas")
@rol_requerido("administrador")
def alertas():
    try:
        datos, error = alertas_ia.alertas(), None
    except alertas_ia.ServicioNoDisponible as e:
        datos, error = None, str(e) if e.args and e.args[0] else None
    return render_template("admin/alertas.html", a=datos, error=error, caido=datos is None,
                           url_ia=alertas_ia.URL_IA)


@bp.route("/clientes")
@rol_requerido("administrador")
def clientes():
    buscar = request.args.get("buscar", "").strip()
    filas = gestion.clientes(buscar)
    return render_template("admin/clientes.html", filas=filas, buscar=buscar,
                           activos=sum(1 for f in filas if f["activo"]))


@bp.route("/usuarios")
@rol_requerido("administrador")
def usuarios():
    filtros = {"buscar": request.args.get("buscar", "")[:40], "rol": request.args.get("rol", ""),
               "estado": request.args.get("estado", "")}
    todos = gestion.usuarios()
    lista = gestion.usuarios(**filtros) if any(filtros.values()) else todos
    limite = datetime.now() - timedelta(minutes=15)
    conectados = {i for i, t in en_linea.items() if t >= limite}
    return render_template("admin/usuarios.html", usuarios=lista, todos=todos,
                           conectados=conectados, filtros=filtros)


@bp.route("/usuarios/nuevo", methods=["GET", "POST"])
@rol_requerido("administrador")
def nuevo_usuario():
    datos = None
    if request.method == "POST":
        datos = request.form
        try:
            gestion.crear_usuario(datos.get("nombre", ""), datos.get("username", ""),
                                  datos.get("rol", ""), datos.get("clave", ""))
            flash(f"Usuario {datos.get('username', '').strip().lower()} creado.")
            return redirect(url_for("admin.usuarios"))
        except ErrorNegocio as e:
            flash(f"{e.titulo}: {e.mensaje}", "error")
    return render_template("admin/usuario.html", u=None, datos=datos)


@bp.route("/usuarios/editar")
@rol_requerido("administrador")
def editar_usuario():
    elegido = request.args.get("id", type=int)
    if elegido and db.session.get(Usuario, elegido):
        return redirect(url_for("admin.usuario", id_usuario=elegido))
    return render_template("admin/elegir_usuario.html", usuarios=gestion.usuarios())


@bp.route("/usuarios/<int:id_usuario>", methods=["GET", "POST"])
@rol_requerido("administrador")
def usuario(id_usuario):
    u = db.session.get(Usuario, id_usuario)
    if u is None:
        flash("Usuario no encontrado: el usuario ya no existe.", "error")
        return redirect(url_for("admin.usuarios"))
    datos = None
    if request.method == "POST":
        try:
            if request.form.get("accion") == "clave":
                flash(f"Se cambió la contraseña de {gestion.cambiar_clave(id_usuario, request.form.get('clave', ''))}.")
            else:
                datos = request.form
                activo = datos.get("activo") == "si"
                nombre = gestion.editar_usuario(id_usuario, datos.get("nombre", ""), datos.get("username", ""),
                                                datos.get("rol", ""), activo, current_user)
                if not activo:
                    en_linea.pop(id_usuario, None)
                flash(f"Se guardaron los cambios de {nombre}.")
            return redirect(url_for("admin.usuarios"))
        except ErrorNegocio as e:
            flash(f"{e.titulo}: {e.mensaje}", "error")
    return render_template("admin/usuario.html", u=u, datos=datos)


@bp.route("/usuarios/eliminar", methods=["GET", "POST"])
@rol_requerido("administrador")
def eliminar_usuario():
    if request.method == "POST":
        id_usuario = request.form.get("id_usuario", "")
        try:
            nombre = gestion.eliminar_usuario(int(id_usuario) if id_usuario.isdigit() else 0, current_user)
            en_linea.pop(int(id_usuario), None)
            flash(f"Se eliminó el usuario {nombre}.")
            return redirect(url_for("admin.usuarios"))
        except ErrorNegocio as e:
            flash(f"{e.titulo}: {e.mensaje}", "error")
            return redirect(url_for("admin.eliminar_usuario", id=id_usuario))
    elegido = request.args.get("id", type=int)
    u = db.session.get(Usuario, elegido) if elegido else None
    return render_template("admin/eliminar_usuario.html", usuarios=gestion.usuarios(), u=u,
                           registros=gestion.registros_usuario(u.id_usuario) if u else 0)


@bp.route("/qr")
@rol_requerido("administrador")
def qr():
    direccion = request.args.get("url") or request.host_url
    imagen = qrcode.make(direccion, image_factory=qrcode.image.svg.SvgPathImage, box_size=12, border=2)
    svg = imagen.to_string(encoding="unicode")
    return render_template("admin/qr.html", direccion=direccion, svg=Markup(svg))
