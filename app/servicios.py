"""Lógica de negocio y coordinación de transacciones de UBite.

Cada función pública que escribe en la base de datos corre dentro de
transaccion(): si cualquier paso falla se hace ROLLBACK y no queda nada a
medias. Las rutas solo llaman a estas funciones y muestran el resultado.
"""
from sqlalchemy import case, exists, func, select

from .database import db, transaccion
from .models import (Cliente, DetallePedido, Notificacion, Pago, Pedido,
                     Producto, Transaccion, ahora)

ESTADOS_ACTIVOS = ("en_cola", "en_preparacion", "listo")


class ErrorNegocio(Exception):
    """Error esperado de una regla de negocio (sin stock, estado no permitido...).
    Lleva un título y un mensaje pensados para mostrarle al usuario."""

    def __init__(self, titulo, mensaje, detalle=None):
        super().__init__(mensaje)
        self.titulo = titulo
        self.mensaje = mensaje
        self.detalle = detalle or []


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------
def menu_por_categoria():
    productos = (Producto.query.filter_by(activo=True)
                 .order_by(Producto.id_categoria, Producto.nombre).all())
    menu = {}
    for p in productos:
        menu.setdefault(p.categoria.nombre, []).append(p)
    return menu


def buscar_pedido(codigo):
    return Pedido.query.filter_by(codigo=codigo.upper().strip()).first()


def _pagado_expr():
    return exists().where(Pago.id_pedido == Pedido.id_pedido, Pago.estado == "aprobado")


def cola_activa():
    """Pedidos en curso en el orden en que se atienden: primero los pagados en
    la aplicación (prioridad) y después por hora de llegada."""
    pagado = _pagado_expr()
    return (Pedido.query.filter(Pedido.estado.in_(ESTADOS_ACTIVOS))
            .order_by(case((pagado, 0), else_=1), Pedido.fecha_hora).all())


def posicion_en_cola(pedido):
    """Cuántos pedidos se van a atender antes que este."""
    if pedido.estado != "en_cola":
        return 0
    cola = [p for p in cola_activa() if p.estado == "en_cola"]
    for i, p in enumerate(cola):
        if p.id_pedido == pedido.id_pedido:
            return i
    return 0


def pedidos_del_dia():
    hoy = ahora().date()
    return (Pedido.query.filter(func.date(Pedido.fecha_hora) == hoy.isoformat())
            .order_by(Pedido.fecha_hora.desc()).all())


# ---------------------------------------------------------------------------
# Operaciones transaccionales
# ---------------------------------------------------------------------------
def _validar_items(items):
    """items: {id_producto: cantidad}. Devuelve [(producto, cantidad)] o lanza
    ErrorNegocio si algún producto no existe, no está activo o no alcanza."""
    if not items:
        raise ErrorNegocio("Tu pedido está vacío", "Agrega al menos un producto antes de confirmar.")
    lineas, faltantes = [], []
    for id_producto, cantidad in items.items():
        producto = db.session.get(Producto, int(id_producto))
        if producto is None or not producto.activo:
            faltantes.append("Un producto ya no está en el menú")
            continue
        if cantidad <= 0:
            continue
        if not producto.validar_stock(cantidad):
            faltantes.append(f"{producto.nombre}: pediste {cantidad}, quedan {producto.stock_actual}")
            continue
        lineas.append((producto, cantidad))
    if faltantes:
        raise ErrorNegocio("No alcanzó el stock",
                           "Mientras armabas tu pedido otra persona compró algunos productos. "
                           "No se registró nada; ajusta las cantidades e intenta de nuevo.",
                           faltantes)
    if not lineas:
        raise ErrorNegocio("Tu pedido está vacío", "Agrega al menos un producto antes de confirmar.")
    return lineas


def _siguiente_codigo():
    # Se calcula dentro de la transacción de escritura, así que no se repite
    ultimo = db.session.execute(select(func.max(Pedido.id_pedido))).scalar() or 0
    return f"UB-{ultimo + 1:04d}"


def registrar_pedido(nombre, telefono, items, origen="qr", usuario=None):
    """Registra cliente, pedido, detalles, descuento de stock y la transacción
    en un solo bloque atómico. Devuelve el código del pedido."""
    nombre, telefono = nombre.strip(), telefono.strip()
    with transaccion():
        lineas = _validar_items(items)

        cliente = Cliente.query.filter_by(telefono=telefono, nombre=nombre).first()
        if cliente is None:
            cliente = Cliente(nombre=nombre, telefono=telefono)
            db.session.add(cliente)

        pedido = Pedido(codigo=_siguiente_codigo(), cliente=cliente, origen=origen,
                        usuario=usuario, estado="en_cola")
        db.session.add(pedido)
        for producto, cantidad in lineas:
            producto.descontar_stock(cantidad)
            pedido.detalles.append(DetallePedido(
                producto=producto, cantidad=cantidad, precio_unitario=producto.precio,
                subtotal=producto.precio * cantidad))
        pedido.calcular_total()

        quien = "por el cajero" if origen == "presencial" else "por QR"
        Transaccion.registrar(pedido, "registro_pedido", usuario=usuario,
                              descripcion=f"Pedido registrado {quien}; stock descontado")
        db.session.flush()
        return pedido.codigo


def modificar_pedido(codigo, items):
    """Cambia las cantidades de un pedido que sigue en cola. Ajusta el stock
    solo por la diferencia y recalcula el total."""
    try:
        _modificar(codigo, items)
    except ErrorNegocio as e:
        if e.detalle:  # falló por stock: se hizo rollback y se deja constancia
            _registrar_revertida(codigo, "modificacion_pedido",
                                 "Modificación revertida por falta de stock: " + "; ".join(e.detalle))
        raise


def _modificar(codigo, items):
    with transaccion():
        pedido = buscar_pedido(codigo)
        if pedido is None:
            raise ErrorNegocio("Pedido no encontrado", "No existe un pedido con ese código.")
        if pedido.estado != "en_cola":
            raise ErrorNegocio("Ya no se puede modificar",
                               "Tu pedido ya está en preparación, así que no se puede cambiar.")
        if pedido.pagado:
            raise ErrorNegocio("Ya no se puede modificar",
                               "Este pedido ya se pagó en la aplicación. Si necesitas algo más, "
                               "haz un pedido nuevo.")

        actuales = {d.id_producto: d for d in pedido.detalles}
        nuevos = {int(k): v for k, v in items.items() if v > 0}
        if not nuevos:
            raise ErrorNegocio("El pedido no puede quedar vacío",
                               "Si ya no quieres nada, mejor cancela el pedido.")

        faltantes = []
        for id_producto in set(actuales) | set(nuevos):
            antes = actuales[id_producto].cantidad if id_producto in actuales else 0
            despues = nuevos.get(id_producto, 0)
            diferencia = despues - antes
            producto = db.session.get(Producto, id_producto)
            if diferencia > 0:
                if not producto.validar_stock(diferencia):
                    faltantes.append(f"{producto.nombre}: quedan {producto.stock_actual} adicionales")
                    continue
                producto.descontar_stock(diferencia)
            elif diferencia < 0:
                producto.devolver_stock(-diferencia)

            if despues == 0:
                pedido.detalles.remove(actuales[id_producto])
            elif id_producto in actuales:
                d = actuales[id_producto]
                d.cantidad, d.subtotal = despues, d.precio_unitario * despues
            else:
                pedido.detalles.append(DetallePedido(
                    producto=producto, cantidad=despues, precio_unitario=producto.precio,
                    subtotal=producto.precio * despues))
        if faltantes:
            raise ErrorNegocio("No alcanzó el stock",
                               "No se hizo ningún cambio en tu pedido.", faltantes)

        pedido.calcular_total()
        Transaccion.registrar(pedido, "modificacion_pedido",
                              descripcion="Cantidades modificadas en cola; stock ajustado")


def cancelar_pedido(codigo, usuario=None):
    """Cancela un pedido en cola y devuelve el stock de sus productos."""
    with transaccion():
        pedido = buscar_pedido(codigo)
        if pedido is None:
            raise ErrorNegocio("Pedido no encontrado", "No existe un pedido con ese código.")
        if pedido.estado != "en_cola":
            raise ErrorNegocio("Ya no se puede cancelar",
                               "El pedido ya está en preparación o fue entregado.")
        if pedido.pagado:
            raise ErrorNegocio("Ya no se puede cancelar",
                               "Este pedido ya se pagó en la aplicación; acércate a la caja.")
        pedido.cambiar_estado("cancelado")
        for d in pedido.detalles:
            d.producto.devolver_stock(d.cantidad)
        quien = "por el cajero" if usuario else "por el cliente"
        Transaccion.registrar(pedido, "cancelacion", usuario=usuario,
                              descripcion=f"Cancelado {quien} en cola; stock devuelto")


def cambiar_estado(id_pedido, nuevo, usuario):
    """en_cola -> en_preparacion -> listo. Al quedar listo se avisa al cliente."""
    with transaccion():
        pedido = db.session.get(Pedido, id_pedido)
        if pedido is None:
            raise ErrorNegocio("Pedido no encontrado", "El pedido ya no existe.")
        anterior = pedido.estado
        try:
            pedido.cambiar_estado(nuevo)
        except ValueError:
            raise ErrorNegocio("Cambio no permitido",
                               f"El pedido {pedido.codigo} está {anterior.replace('_', ' ')}.")
        Transaccion.registrar(pedido, "cambio_estado", usuario=usuario,
                              descripcion=f"{anterior} -> {nuevo}")
        if nuevo == "listo":
            if pedido.pagado:
                mensaje = f"Tu pedido {pedido.codigo} está listo. Ya está pago, solo acércate a recogerlo."
            else:
                mensaje = f"Tu pedido {pedido.codigo} está listo. Acércate a la caja para pagar y recogerlo."
            db.session.add(Notificacion(pedido=pedido, mensaje=mensaje, canal="pagina",
                                        estado="enviada", fecha_envio=ahora()))
        return pedido.codigo


def entregar_pedido(id_pedido, usuario):
    """Entrega un pedido listo. Si no se pagó en la app, en la misma
    transacción se registra el cobro en efectivo."""
    with transaccion():
        pedido = db.session.get(Pedido, id_pedido)
        if pedido is None:
            raise ErrorNegocio("Pedido no encontrado", "El pedido ya no existe.")
        if pedido.estado != "listo":
            raise ErrorNegocio("Cambio no permitido",
                               f"El pedido {pedido.codigo} todavía no está listo.")
        pedido.cambiar_estado("entregado")
        if pedido.pagado:
            Transaccion.registrar(pedido, "cambio_estado", usuario=usuario,
                                  descripcion="listo -> entregado (pagado en la app)")
        else:
            db.session.add(Pago(pedido=pedido, usuario=usuario, metodo="efectivo",
                                medio="efectivo", estado="aprobado", monto=pedido.total))
            Transaccion.registrar(pedido, "pago", usuario=usuario,
                                  descripcion="Cobro en caja al entregar; listo -> entregado")
        return pedido.codigo


def marcar_notificaciones_vistas(pedido):
    ids = [n.id_notificacion for n in pedido.notificaciones if n.estado == "enviada"]
    if not ids:
        return
    with transaccion():
        for i in ids:
            db.session.get(Notificacion, i).estado = "vista"


def _registrar_revertida(codigo, tipo, descripcion):
    """Deja constancia de una operación que se deshizo con ROLLBACK. Va en su
    propia transacción, porque la original ya no guardó nada."""
    with transaccion():
        pedido = buscar_pedido(codigo)
        if pedido is not None:
            Transaccion.registrar(pedido, tipo, resultado="revertida", descripcion=descripcion)
