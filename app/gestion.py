from collections import Counter, defaultdict
from datetime import timedelta

from sqlalchemy import func
from werkzeug.security import generate_password_hash

from .database import db, transaccion
from .models import Categoria, Cliente, Pedido, Producto, Usuario, ahora
from .servicios import ACTIVOS, ErrorNegocio


# reporte del dia

def _pedidos_de(fecha):
    return Pedido.query.filter(func.date(Pedido.fecha_hora) == fecha.isoformat()).all()


def _pago(pedido):
    return next((p for p in pedido.pagos if p.estado == "aprobado"), None)


def reporte(fecha):
    pedidos = _pedidos_de(fecha)
    validos = [p for p in pedidos if p.estado != "cancelado"]
    pagados = [(p, _pago(p)) for p in validos if _pago(p)]
    total = sum(pago.monto for _, pago in pagados)
    en_app = sum(1 for _, pago in pagados if pago.metodo == "app")

    ayer = sum(_pago(p).monto for p in _pedidos_de(fecha - timedelta(days=1))
               if p.estado != "cancelado" and _pago(p))

    por_hora = defaultdict(float)
    for p, pago in pagados:
        por_hora[p.fecha_hora.hour] += pago.monto
    horas = []
    if por_hora:
        tope = max(por_hora.values())
        picos = sorted(por_hora, key=por_hora.get, reverse=True)[:2]
        # se muestra al menos la jornada normal de la cafeteria (6 a. m. a 8 p. m.)
        for h in range(min(6, min(por_hora)), max(20, max(por_hora)) + 1):
            horas.append({"hora": h, "valor": por_hora.get(h, 0),
                          "alto": por_hora.get(h, 0) / tope * 100, "pico": h in picos})

    vendidos = Counter()
    for p, _ in pagados:
        for d in p.detalles:
            vendidos[d.producto.nombre] += d.subtotal

    return {
        "total": total,
        "ayer": ayer,
        "variacion": round((total - ayer) / ayer * 100) if ayer else None,
        "pedidos": len(validos),
        "qr": sum(1 for p in validos if p.origen == "qr"),
        "presenciales": sum(1 for p in validos if p.origen == "presencial"),
        "cancelados": len(pedidos) - len(validos),
        "pagados": len(pagados),
        "en_app": en_app,
        "en_efectivo": len(pagados) - en_app,
        "pct_app": round(en_app / len(pagados) * 100) if pagados else 0,
        "ticket": total / len(pagados) if pagados else 0,
        "horas": horas,
        "mas_vendidos": vendidos.most_common(5),
        "lista": sorted(pedidos, key=lambda p: p.fecha_hora),
    }


# inventario

def estado_producto(p):
    if not p.activo:
        return "inactivo"
    if p.stock_actual == 0:
        return "agotado"
    if p.stock_actual <= p.stock_minimo:
        return "stock bajo"
    return "activo"


def inventario():
    return (Producto.query.join(Categoria)
            .order_by(Categoria.nombre, Producto.nombre).all())


def entrada_stock(id_producto, cantidad):
    if cantidad <= 0:
        raise ErrorNegocio("Cantidad no válida", "La entrada debe ser mayor que cero.")
    with transaccion():
        p = db.session.get(Producto, id_producto)
        if p is None:
            raise ErrorNegocio("Producto no encontrado", "El producto ya no existe.")
        p.stock_actual += cantidad
        return p.nombre, p.stock_actual


def guardar_producto(datos, id_producto=None):
    nombre = datos.get("nombre", "").strip()
    categoria = datos.get("categoria", "").strip()
    try:
        precio = float(datos.get("precio", 0))
        stock = int(datos.get("stock_actual", 0))
        minimo = int(datos.get("stock_minimo", 0))
    except ValueError:
        raise ErrorNegocio("Datos no válidos", "Precio y cantidades deben ser números.")
    if not nombre or not categoria:
        raise ErrorNegocio("Faltan datos", "El producto necesita nombre y categoría.")
    if precio <= 0 or stock < 0 or minimo < 0:
        raise ErrorNegocio("Datos no válidos", "El precio debe ser mayor que cero y el stock no puede ser negativo.")

    with transaccion():
        cat = Categoria.query.filter(func.lower(Categoria.nombre) == categoria.lower()).first()
        if cat is None:
            cat = Categoria(nombre=categoria)
            db.session.add(cat)
        p = db.session.get(Producto, id_producto) if id_producto else Producto()
        if p is None:
            raise ErrorNegocio("Producto no encontrado", "El producto ya no existe.")
        p.nombre, p.descripcion, p.precio = nombre, datos.get("descripcion", "").strip() or None, precio
        p.stock_actual, p.stock_minimo, p.categoria = stock, minimo, cat
        p.activo = datos.get("activo") == "si"
        db.session.add(p)
        return p.nombre


# clientes y usuarios

def clientes(buscar=""):
    q = Cliente.query
    if buscar:
        q = q.filter(Cliente.nombre.ilike(f"%{buscar}%") | Cliente.telefono.like(f"%{buscar}%"))
    filas = []
    for c in q.all():
        hechos = [p for p in c.pedidos if p.estado != "cancelado"]
        filas.append({
            "cliente": c,
            "pedidos": len(c.pedidos),
            "gastado": sum(p.total for p in hechos if p.estado == "entregado"),
            "ultimo": max((p.fecha_hora for p in c.pedidos), default=None),
            "activo": any(p.estado in ACTIVOS for p in c.pedidos),
        })
    filas.sort(key=lambda f: (not f["activo"], f["ultimo"] is None, -(f["ultimo"].timestamp() if f["ultimo"] else 0)))
    return filas


def crear_usuario(nombre, username, rol, clave):
    nombre, username = nombre.strip(), username.strip().lower()
    if not nombre or not username or rol not in ("cajero", "administrador"):
        raise ErrorNegocio("Faltan datos", "Escribe nombre, usuario y rol.")
    if len(clave) < 8:
        raise ErrorNegocio("Contraseña corta", "La contraseña debe tener al menos 8 caracteres.")
    with transaccion():
        if Usuario.query.filter_by(username=username).first():
            raise ErrorNegocio("Usuario repetido", f"Ya existe el usuario {username}.")
        db.session.add(Usuario(nombre=nombre, username=username, rol=rol,
                               password_hash=generate_password_hash(clave)))


def cambiar_activo(id_usuario, quien):
    with transaccion():
        u = db.session.get(Usuario, id_usuario)
        if u is None:
            raise ErrorNegocio("Usuario no encontrado", "El usuario ya no existe.")
        if u.id_usuario == quien.id_usuario:
            raise ErrorNegocio("No permitido", "No puedes desactivar tu propio usuario.")
        u.activo = not u.activo
        return u.username, u.activo


def cambiar_clave(id_usuario, clave):
    if len(clave) < 8:
        raise ErrorNegocio("Contraseña corta", "La contraseña debe tener al menos 8 caracteres.")
    with transaccion():
        u = db.session.get(Usuario, id_usuario)
        u.password_hash = generate_password_hash(clave)
        return u.username


def hoy():
    return ahora().date()
