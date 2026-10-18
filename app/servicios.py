from sqlalchemy import case, exists, func

from .database import db, transaccion
from .models import (Cliente, DetallePedido, Notificacion, Pago, Pedido,
                     Producto, Transaccion, ahora)

ACTIVOS = ("en_cola", "en_preparacion", "listo")


class ErrorNegocio(Exception):
    def __init__(self, titulo, mensaje, detalle=None):
        super().__init__(mensaje)
        self.titulo = titulo
        self.mensaje = mensaje
        self.detalle = detalle or []


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


def _validar(items):
    if not items:
        raise ErrorNegocio("Tu pedido está vacío", "Agrega al menos un producto.")
    lineas, faltan = [], []
    for id_producto, cantidad in items.items():
        if cantidad <= 0:
            continue
        p = db.session.get(Producto, int(id_producto))
        if p is None or not p.activo:
            faltan.append("Un producto ya no está en el menú")
        elif not p.validar_stock(cantidad):
            faltan.append(f"{p.nombre}: pediste {cantidad}, quedan {p.stock_actual}")
        else:
            lineas.append((p, cantidad))
    if faltan:
        raise ErrorNegocio("No alcanzó el stock",
                           "Alguien compró antes que tú. No se guardó nada, ajusta las "
                           "cantidades e intenta otra vez.", faltan)
    if not lineas:
        raise ErrorNegocio("Tu pedido está vacío", "Agrega al menos un producto.")
    return lineas


def siguiente_codigo(origen):
    # A-001 para pedidos por QR, P-001 para los que se toman en caja
    letra = "P" if origen == "presencial" else "A"
    codigos = db.session.scalars(
        db.select(Pedido.codigo).where(Pedido.codigo.like(f"{letra}-%"))).all()
    numeros = [int(c[2:]) for c in codigos if c[2:].isdigit()]
    return f"{letra}-{max(numeros, default=0) + 1:03d}"


def registrar_pedido(nombre, telefono, items, origen="qr", usuario=None):
    with transaccion():
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


def modificar_pedido(codigo, items):
    try:
        _modificar(codigo, items)
    except ErrorNegocio as e:
        if e.detalle:
            # el cambio se deshizo, pero queda la constancia
            with transaccion():
                pedido = buscar_pedido(codigo)
                Transaccion.registrar(pedido, "modificacion_pedido", resultado="revertida",
                                      descripcion="Sin stock: " + "; ".join(e.detalle))
        raise


def _modificar(codigo, items):
    with transaccion():
        pedido = buscar_pedido(codigo)
        if pedido is None:
            raise ErrorNegocio("Pedido no encontrado", "No existe un pedido con ese código.")
        if pedido.estado != "en_cola" or pedido.pagado:
            raise ErrorNegocio("Ya no se puede modificar",
                               "El pedido ya está en preparación o ya se pagó.")

        antes = {d.id_producto: d for d in pedido.detalles}
        despues = {int(k): v for k, v in items.items() if v > 0}
        if not despues:
            raise ErrorNegocio("El pedido no puede quedar vacío",
                               "Si ya no quieres nada, cancela el pedido.")

        faltan = []
        for id_producto in set(antes) | set(despues):
            p = db.session.get(Producto, id_producto)
            viejo = antes[id_producto].cantidad if id_producto in antes else 0
            nuevo = despues.get(id_producto, 0)
            if nuevo > viejo:
                if not p.validar_stock(nuevo - viejo):
                    faltan.append(f"{p.nombre}: solo quedan {p.stock_actual} más")
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
            raise ErrorNegocio("No alcanzó el stock", "No se cambió nada de tu pedido.", faltan)

        pedido.calcular_total()
        Transaccion.registrar(pedido, "modificacion_pedido",
                              descripcion="Cantidades cambiadas en cola; stock ajustado")


def cancelar_pedido(codigo, usuario=None):
    with transaccion():
        pedido = buscar_pedido(codigo)
        if pedido is None:
            raise ErrorNegocio("Pedido no encontrado", "No existe un pedido con ese código.")

        pago = next((p for p in pedido.pagos if p.estado == "aprobado"), None)
        if usuario is None:
            # el cliente solo cancela mientras esta en cola y sin pagar
            if pedido.estado != "en_cola" or pago:
                raise ErrorNegocio("Ya no se puede cancelar",
                                   "Tu pedido ya está en preparación o ya se pagó. "
                                   "Acércate a la caja.")
            nota = "Cancelado por el cliente en cola"
        else:
            if pedido.estado not in ACTIVOS:
                raise ErrorNegocio("Ya no se puede cancelar",
                                   f"El pedido {pedido.codigo} ya fue entregado o cancelado.")
            if pago and pago.metodo == "app":
                raise ErrorNegocio("Pagado en la app",
                                   "La devolución de un pago en línea se hace por la pasarela.")
            nota = f"Cancelado en caja estando {pedido.estado.replace('_', ' ')}"
            if pago:
                nota += f"; se devolvieron $ {pago.monto:,.0f} en efectivo".replace(",", ".")

        pedido.cambiar_estado("cancelado")
        for d in pedido.detalles:
            d.producto.devolver_stock(d.cantidad)
        Transaccion.registrar(pedido, "cancelacion", usuario=usuario,
                              descripcion=nota + "; stock devuelto")


def cambiar_estado(id_pedido, nuevo, usuario):
    with transaccion():
        pedido = db.session.get(Pedido, id_pedido)
        if pedido is None:
            raise ErrorNegocio("Pedido no encontrado", "El pedido ya no existe.")
        anterior = pedido.estado
        try:
            pedido.cambiar_estado(nuevo)
        except ValueError:
            raise ErrorNegocio("Cambio no permitido",
                               f"{pedido.codigo} está {anterior.replace('_', ' ')}.")
        Transaccion.registrar(pedido, "cambio_estado", usuario=usuario,
                              descripcion=f"{anterior} -> {nuevo}")
        if nuevo == "listo":
            if pedido.pagado:
                texto = f"Tu pedido {pedido.codigo} está listo. Ya está pago, solo acércate a recogerlo."
            else:
                texto = f"Tu pedido {pedido.codigo} está listo. Acércate a la caja para pagar y recogerlo."
            db.session.add(Notificacion(pedido=pedido, mensaje=texto, canal="pagina",
                                        estado="enviada", fecha_envio=ahora()))
        return pedido.codigo


def entregar_pedido(id_pedido, usuario):
    with transaccion():
        pedido = db.session.get(Pedido, id_pedido)
        if pedido is None:
            raise ErrorNegocio("Pedido no encontrado", "El pedido ya no existe.")
        if pedido.estado != "listo":
            raise ErrorNegocio("Cambio no permitido", f"{pedido.codigo} todavía no está listo.")
        pedido.cambiar_estado("entregado")
        if pedido.pagado:
            Transaccion.registrar(pedido, "cambio_estado", usuario=usuario,
                                  descripcion="listo -> entregado")
        else:
            db.session.add(Pago(pedido=pedido, usuario=usuario, metodo="efectivo",
                                medio="efectivo", estado="aprobado", monto=pedido.total))
            Transaccion.registrar(pedido, "pago", usuario=usuario,
                                  descripcion="Cobro en caja al entregar; listo -> entregado")
        return pedido.codigo


def marcar_vistas(pedido):
    ids = [n.id_notificacion for n in pedido.notificaciones if n.estado == "enviada"]
    if ids:
        with transaccion():
            for i in ids:
                db.session.get(Notificacion, i).estado = "vista"
