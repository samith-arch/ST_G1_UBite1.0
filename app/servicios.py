import re

from sqlalchemy import case, exists, func

from .database import db, reintentar, transaccion
import logging
from functools import wraps

from .database import BaseOcupada
from .models import (Cliente, DetallePedido, Notificacion, OperacionRechazada, Pago, Pedido,
                     Producto, Transaccion, ahora)

ACTIVOS = ("en_cola", "en_preparacion", "listo")

# letras (con tildes), espacios, punto, guion y apostrofe; entre 2 y 60 caracteres
NOMBRE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .-]{1,59}$")
CELULAR = re.compile(r"^3\d{9}$")


def limpiar_nombre(texto):
    # quita espacios repetidos y devuelve None si no parece un nombre
    nombre = " ".join((texto or "").split())
    return nombre if NOMBRE.match(nombre) else None


class ErrorNegocio(Exception):
    # titulo y mensaje se muestran al usuario; filas es el cuadro "que paso"
    def __init__(self, titulo, mensaje, detalle=None, etiqueta=None, filas=None,
                 nota=None, faltantes=None, motivo=None):
        super().__init__(mensaje)
        self.titulo = titulo
        self.motivo = motivo or titulo
        self.mensaje = mensaje
        self.detalle = detalle or []
        self.etiqueta = etiqueta
        self.filas = filas or []
        self.nota = nota
        self.faltantes = faltantes or {}


def registrar_rechazo(operacion, motivo, detalle, codigo=None, usuario=None, origen=None):
    # la operacion ya se deshizo; el rechazo se guarda aparte para que quede en el historial
    try:
        with transaccion("registrar_rechazo"):
            pedido = buscar_pedido(codigo) if codigo else None
            db.session.add(OperacionRechazada(
                pedido=pedido, id_usuario=usuario.id_usuario if usuario else None,
                operacion=operacion, origen=origen or (pedido.origen if pedido else None),
                motivo=motivo, detalle=(detalle or "")[:400]))
    except Exception:
        logging.getLogger("ubite").exception("no se pudo guardar el rechazo de %s", operacion)


def con_rechazo(operacion, datos):
    # datos(args, kwargs) -> (codigo, usuario, origen) para saber a quien pertenece el intento
    def decorador(funcion):
        @wraps(funcion)
        def envoltura(*args, **kwargs):
            try:
                return funcion(*args, **kwargs)
            except ErrorNegocio as e:
                codigo, usuario, origen = datos(args, kwargs)
                registrar_rechazo(operacion, e.motivo, getattr(e, "resumen", None) or e.mensaje,
                                  codigo, usuario, origen)
                raise
            except BaseOcupada:
                codigo, usuario, origen = datos(args, kwargs)
                registrar_rechazo(operacion, "Base de datos ocupada",
                                  "Otra operación tenía la base ocupada y se agotaron los reintentos.",
                                  codigo, usuario, origen)
                raise
        return envoltura
    return decorador


def menu_por_categoria():
    productos = (Producto.query.filter_by(activo=True)
                 .order_by(Producto.id_categoria, Producto.nombre).all())
    menu = {}
    for p in productos:
        menu.setdefault(p.categoria.nombre, []).append(p)
    return menu


def buscar_pedido(codigo):
    return Pedido.query.filter_by(codigo=codigo.upper().strip()).first()


def cola_activa():
    # primero los que ya estan pagos, despues por hora de llegada
    pagado = exists().where(Pago.id_pedido == Pedido.id_pedido, Pago.estado == "aprobado")
    return (Pedido.query.filter(Pedido.estado.in_(ACTIVOS))
            .order_by(case((pagado, 0), else_=1), Pedido.fecha_hora).all())


def posicion_en_cola(pedido):
    if pedido.estado != "en_cola":
        return 0
    cola = [p.id_pedido for p in cola_activa() if p.estado == "en_cola"]
    return cola.index(pedido.id_pedido) if pedido.id_pedido in cola else 0


def pedidos_del_dia():
    hoy = ahora().date().isoformat()
    return (Pedido.query.filter(func.date(Pedido.fecha_hora) == hoy)
            .order_by(Pedido.fecha_hora.desc()).all())


def _sin_stock(faltan, nombres):
    # pantalla E1 de figma
    if len(nombres) == 1:
        titulo = f"{nombres[0]} se agotó mientras confirmabas"
    else:
        titulo = "Algunos productos se agotaron mientras confirmabas"
    filas = [(n, t) for n, t in faltan.items()]
    filas += [("Pedido", "no se guardó"), ("Stock de los demás", "sin cambios"), ("Cobro", "ninguno")]
    e = ErrorNegocio(titulo,
                        "Otra persona pidió la última unidad un instante antes. Para no venderte "
                        "algo que no hay, el sistema deshizo la operación completa.",
                        etiqueta="Pedido no registrado", filas=filas,
                        nota="Rollback: como un paso falló, ningún paso quedó guardado.",
                        motivo="Sin stock suficiente")
    e.agotados = nombres
    e.resumen = "; ".join(f"{n}: {t}" for n, t in faltan.items())
    return e


def _validar(items):
    if not any(c > 0 for c in items.values()):
        raise ErrorNegocio("Tu pedido está vacío", "Agrega al menos un producto.", motivo="Pedido vacío")
    lineas, faltan, nombres, disponibles = [], {}, [], {}
    for id_producto, cantidad in items.items():
        if cantidad <= 0:
            continue
        p = db.session.get(Producto, int(id_producto))
        if p is None or not p.activo:
            faltan["Producto retirado"] = "ya no está en el menú"
            disponibles[int(id_producto)] = 0
        elif not p.validar_stock(cantidad):
            faltan[p.nombre] = f"pediste {cantidad} · quedan {p.stock_actual}"
            nombres.append(p.nombre)
            disponibles[p.id_producto] = p.stock_actual
        else:
            lineas.append((p, cantidad))
    if faltan:
        e = _sin_stock(faltan, nombres or ["Un producto"])
        e.faltantes = disponibles
        raise e
    return lineas


def siguiente_codigo(origen):
    # A-001 para pedidos por QR, P-001 para los que se toman en caja
    letra = "P" if origen == "presencial" else "A"
    codigos = db.session.scalars(
        db.select(Pedido.codigo).where(Pedido.codigo.like(f"{letra}-%"))).all()
    numeros = [int(c[2:]) for c in codigos if c[2:].isdigit()]
    return f"{letra}-{max(numeros, default=0) + 1:03d}"


def _datos_registro(a, k):
    return None, k.get("usuario", a[4] if len(a) > 4 else None), k.get("origen", a[3] if len(a) > 3 else "qr")


@con_rechazo("registro_pedido", _datos_registro)
@reintentar
def registrar_pedido(nombre, telefono, items, origen="qr", usuario=None):
    nombre = limpiar_nombre(nombre)
    if nombre is None:
        raise ErrorNegocio("Nombre no válido", "El nombre solo puede tener letras y espacios (2 a 60 caracteres).",
                          motivo="Datos del cliente no válidos")
    if (telefono or origen == "qr") and not CELULAR.match(telefono or ""):
        raise ErrorNegocio("Celular no válido", "El celular debe tener 10 dígitos y empezar por 3.",
                          motivo="Datos del cliente no válidos")
    with transaccion("registrar_pedido"):
        lineas = _validar(items)

        cliente = Cliente.query.filter_by(nombre=nombre, telefono=telefono).first()
        if cliente is None:
            cliente = Cliente(nombre=nombre, telefono=telefono)
            db.session.add(cliente)

        # el pedido en caja se cobra de una vez y pasa directo a preparacion
        presencial = origen == "presencial"
        pedido = Pedido(codigo=siguiente_codigo(origen), cliente=cliente, origen=origen,
                        usuario=usuario, estado="en_preparacion" if presencial else "en_cola")
        db.session.add(pedido)
        for p, cantidad in lineas:
            p.descontar_stock(cantidad)
            pedido.detalles.append(DetallePedido(producto=p, cantidad=cantidad,
                                                 precio_unitario=p.precio,
                                                 subtotal=p.precio * cantidad))
        pedido.calcular_total()

        if presencial:
            Transaccion.registrar(pedido, "registro_pedido", usuario=usuario,
                                  descripcion="Pedido presencial registrado; stock descontado")
            db.session.add(Pago(pedido=pedido, usuario=usuario, metodo="efectivo",
                                medio="efectivo", estado="aprobado", monto=pedido.total))
            Transaccion.registrar(pedido, "pago", usuario=usuario,
                                  descripcion="Cobro en caja al registrar el pedido")
        else:
            Transaccion.registrar(pedido, "registro_pedido",
                                  descripcion="Pedido registrado por QR; stock descontado")
        db.session.flush()
        return pedido.codigo


@con_rechazo("modificacion_pedido", lambda a, k: (a[0], None, None))
@reintentar
def modificar_pedido(codigo, items):
    _modificar(codigo, items)


def _modificar(codigo, items):
    with transaccion("modificar_pedido"):
        pedido = buscar_pedido(codigo)
        if pedido is None:
            raise ErrorNegocio("Pedido no encontrado", "No existe un pedido con ese código.")
        if pedido.estado != "en_cola" or pedido.pagado:
            raise ErrorNegocio("Ya no se puede modificar",
                               "El pedido ya está en preparación o ya se pagó.",
                               etiqueta="Operación rechazada", motivo="El estado del pedido no lo permite")

        antes = {d.id_producto: d for d in pedido.detalles}
        despues = {int(k): v for k, v in items.items() if v > 0}
        if not despues:
            raise ErrorNegocio("El pedido no puede quedar vacío",
                               "Si ya no quieres nada, cancela el pedido.")

        faltan, nombres, disponibles = {}, [], {}
        for id_producto in set(antes) | set(despues):
            p = db.session.get(Producto, id_producto)
            viejo = antes[id_producto].cantidad if id_producto in antes else 0
            nuevo = despues.get(id_producto, 0)
            if nuevo > viejo:
                if not p.validar_stock(nuevo - viejo):
                    faltan[p.nombre] = f"pediste {nuevo - viejo} más · quedan {p.stock_actual}"
                    nombres.append(p.nombre)
                    disponibles[p.id_producto] = p.stock_actual + viejo
                    continue
                p.descontar_stock(nuevo - viejo)
            elif nuevo < viejo:
                p.devolver_stock(viejo - nuevo)

            if nuevo == 0:
                pedido.detalles.remove(antes[id_producto])
            elif id_producto in antes:
                antes[id_producto].cantidad = nuevo
                antes[id_producto].subtotal = antes[id_producto].precio_unitario * nuevo
            else:
                pedido.detalles.append(DetallePedido(producto=p, cantidad=nuevo,
                                                     precio_unitario=p.precio,
                                                     subtotal=p.precio * nuevo))
        if faltan:
            e = _sin_stock(faltan, nombres)
            e.etiqueta = "Cambio no guardado"
            e.filas[-3] = ("Pedido", "quedó como estaba")
            e.faltantes = disponibles
            e.resumen = "; ".join(f"{n}: {t}" for n, t in faltan.items())
            raise e

        pedido.calcular_total()
        Transaccion.registrar(pedido, "modificacion_pedido",
                              descripcion="Cantidades cambiadas en cola; stock ajustado")


@con_rechazo("cancelacion", lambda a, k: (a[0], k.get("usuario", a[1] if len(a) > 1 else None), None))
@reintentar
def cancelar_pedido(codigo, usuario=None):
    with transaccion("cancelar_pedido"):
        pedido = buscar_pedido(codigo)
        if pedido is None:
            raise ErrorNegocio("Pedido no encontrado", "No existe un pedido con ese código.")

        pago = next((p for p in pedido.pagos if p.estado == "aprobado"), None)
        if usuario is None:
            # el cliente solo cancela mientras esta en cola y sin pagar
            if pedido.estado != "en_cola" or pago:
                raise ErrorNegocio("Ya no se puede cancelar",
                                   "Tu pedido ya está en preparación o ya se pagó. "
                                   "Acércate a la caja.", etiqueta="Operación rechazada",
                                   motivo="El estado del pedido no lo permite")
            nota = "Cancelado por el cliente en cola"
        else:
            if pedido.estado not in ACTIVOS:
                raise ErrorNegocio("Ya no se puede cancelar",
                                   f"El pedido {pedido.codigo} ya fue entregado o cancelado.",
                                   motivo="El estado del pedido no lo permite")
            nota = f"Cancelado en caja estando {pedido.estado.replace('_', ' ')}"
            if pago:
                nota += f"; se devolvieron $ {pago.monto:,.0f} en efectivo".replace(",", ".")

        pedido.cambiar_estado("cancelado")
        for d in pedido.detalles:
            d.producto.devolver_stock(d.cantidad)
        Transaccion.registrar(pedido, "cancelacion", usuario=usuario,
                              descripcion=nota + "; stock devuelto")


def _codigo_de(id_pedido):
    p = db.session.get(Pedido, id_pedido)
    return p.codigo if p else None


@con_rechazo("cambio_estado", lambda a, k: (_codigo_de(a[0]), a[2] if len(a) > 2 else k.get("usuario"), None))
@reintentar
def cambiar_estado(id_pedido, nuevo, usuario):
    # devuelve el codigo y, si quedo listo y hay suscripcion, el aviso push a enviar
    with transaccion("cambiar_estado"):
        pedido = db.session.get(Pedido, id_pedido)
        if pedido is None:
            raise ErrorNegocio("Pedido no encontrado", "El pedido ya no existe.")
        anterior = pedido.estado
        try:
            pedido.cambiar_estado(nuevo)
        except ValueError:
            raise ErrorNegocio("Cambio no permitido",
                               f"{pedido.codigo} está {anterior.replace('_', ' ')}. "
                               "Puede que otra persona ya lo haya movido.",
                               motivo="Cambio de estado no permitido")
        Transaccion.registrar(pedido, "cambio_estado", usuario=usuario,
                              descripcion=f"{anterior} -> {nuevo}")
        aviso = None
        if nuevo == "listo":
            if pedido.pagado:
                texto = "Ya está pago, solo acércate a recogerlo."
            else:
                texto = "Acércate a la caja con tu código para pagar y recogerlo."
            # si el cliente activo los avisos se manda push; si no, queda en la pagina
            canal = "push" if pedido.cliente.suscripcion_push else "pagina"
            aviso = Notificacion(pedido=pedido, mensaje=texto, canal=canal,
                                 estado="pendiente" if canal == "push" else "enviada",
                                 fecha_envio=None if canal == "push" else ahora())
            db.session.add(aviso)
        db.session.flush()
        return pedido.codigo, (aviso.id_notificacion if aviso and aviso.canal == "push" else None)


@reintentar
def entregar_pedido(id_pedido, usuario, cobrar=False):
    with transaccion("entregar_pedido"):
        pedido = db.session.get(Pedido, id_pedido)
        if pedido is None:
            raise ErrorNegocio("Pedido no encontrado", "El pedido ya no existe.")
        if pedido.estado != "listo":
            raise ErrorNegocio("Cambio no permitido",
                               f"{pedido.codigo} está {pedido.estado.replace('_', ' ')}. "
                               "Puede que otra persona ya lo haya entregado.",
                               motivo="Cambio de estado no permitido")
        pago = next((p for p in pedido.pagos if p.estado == "aprobado"), None)
        if cobrar and pago:
            # el cajero vio el pedido sin pagar, pero mientras tanto se pago (E5)
            codigo, cuando, metodo = pedido.codigo, pago.fecha, pago.metodo
            raise ErrorNegocio(
                "Este pedido ya está pagado",
                f"El pedido {codigo} se pagó {'en la app' if metodo == 'app' else 'en caja'} a las "
                f"{cuando:%I:%M %p}. Para no registrar dos pagos del mismo pedido, el sistema no "
                "aplicó el cobro en efectivo.",
                etiqueta="Operación rechazada",
                filas=[(f"Pedido {codigo}", "pagado en la app" if metodo == "app" else "pagado en caja"),
                       ("Referencia", pago.referencia or "efectivo"),
                       ("Intento", "pago en efectivo"), ("Resultado", "revertido")],
                nota="La transacción se revirtió y el intento quedó registrado en el historial.",
                motivo="Pago duplicado")
        pedido.cambiar_estado("entregado")
        if pago:
            Transaccion.registrar(pedido, "cambio_estado", usuario=usuario,
                                  descripcion="listo -> entregado")
        else:
            db.session.add(Pago(pedido=pedido, usuario=usuario, metodo="efectivo",
                                medio="efectivo", estado="aprobado", monto=pedido.total))
            Transaccion.registrar(pedido, "pago", usuario=usuario,
                                  descripcion="Cobro en caja al entregar; listo -> entregado")
        return pedido.codigo


@con_rechazo("pago", lambda a, k: (_codigo_de(a[0]), a[1], None))
def entregar_o_rechazar(id_pedido, usuario, cobrar):
    return entregar_pedido(id_pedido, usuario, cobrar)


@reintentar
def guardar_suscripcion(codigo, suscripcion):
    with transaccion("guardar_suscripcion"):
        pedido = buscar_pedido(codigo)
        if pedido is None:
            raise ErrorNegocio("Pedido no encontrado", "No existe un pedido con ese código.")
        pedido.cliente.suscripcion_push = suscripcion


def marcar_vistas(pedido):
    ids = [n.id_notificacion for n in pedido.notificaciones if n.estado == "enviada"]
    if ids:
        with transaccion("marcar_vistas"):
            for i in ids:
                db.session.get(Notificacion, i).estado = "vista"
