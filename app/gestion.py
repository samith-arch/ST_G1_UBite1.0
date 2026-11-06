import re
from collections import Counter, defaultdict
from datetime import timedelta

from sqlalchemy import func
from werkzeug.security import generate_password_hash

from .database import db, reintentar, transaccion
from .models import (Categoria, Cliente, DetallePedido, Pago, Pedido, Producto, Transaccion,
                     Usuario, ahora)
from .servicios import ACTIVOS, ErrorNegocio, limpiar_nombre

MAX_STOCK = 9999
MAX_ENTRADA = 1000
USUARIO = re.compile(r"^[a-z0-9.]{3,20}$")


def _entero(valor, campo, minimo, maximo):
    texto = str(valor or "").strip()
    if not texto.isdigit():
        raise ErrorNegocio("Datos no válidos", f"{campo} debe ser un número entero, sin puntos ni letras.")
    n = int(texto)
    if not minimo <= n <= maximo:
        raise ErrorNegocio("Datos no válidos", f"{campo} debe estar entre {minimo} y {maximo}.")
    return n


# reporte por dia, semana, mes o año

PERIODOS = ("dia", "semana", "mes", "anio")
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def rango(fecha, periodo):
    # devuelve el primer y el ultimo dia del periodo que contiene a la fecha
    if periodo == "semana":
        desde = fecha - timedelta(days=fecha.weekday())
        return desde, desde + timedelta(days=6)
    if periodo == "mes":
        desde = fecha.replace(day=1)
        siguiente = (desde + timedelta(days=32)).replace(day=1)
        return desde, siguiente - timedelta(days=1)
    if periodo == "anio":
        return fecha.replace(month=1, day=1), fecha.replace(month=12, day=31)
    return fecha, fecha


def _pedidos_entre(desde, hasta):
    return Pedido.query.filter(func.date(Pedido.fecha_hora) >= desde.isoformat(),
                               func.date(Pedido.fecha_hora) <= hasta.isoformat()).all()


def _pago(pedido):
    return next((p for p in pedido.pagos if p.estado == "aprobado"), None)


def _barras(pagados, periodo, desde, hasta):
    # agrupa las ventas segun el periodo: por hora, por dia o por mes
    if periodo == "dia":
        clave = lambda p: p.fecha_hora.hour
    elif periodo == "anio":
        clave = lambda p: p.fecha_hora.month
    else:
        clave = lambda p: p.fecha_hora.date()
    suma = defaultdict(float)
    for p, pago in pagados:
        suma[clave(p)] += pago.monto
    if not suma:
        return []

    if periodo == "dia":
        # al menos la jornada normal de la cafeteria (6 a. m. a 8 p. m.)
        claves = range(min(6, min(suma)), max(20, max(suma)) + 1)
        texto = lambda h: str(12 if h % 12 == 0 else h % 12)
        titulo = lambda h: f"{h}:00"
    elif periodo == "anio":
        claves = range(1, 13)
        texto = lambda m: MESES[m - 1]
        titulo = lambda m: MESES[m - 1]
    else:
        claves = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]
        texto = (lambda d: DIAS[d.weekday()]) if periodo == "semana" else (lambda d: str(d.day))
        titulo = lambda d: f"{DIAS[d.weekday()]} {d.day}/{d.month}"

    tope = max(suma.values())
    picos = sorted(suma, key=suma.get, reverse=True)[:2]
    return [{"texto": texto(k), "titulo": titulo(k), "valor": suma.get(k, 0),
             "alto": suma.get(k, 0) / tope * 100, "pico": k in picos} for k in claves]


def _total(pedidos):
    return sum(_pago(p).monto for p in pedidos if p.estado != "cancelado" and _pago(p))


def reporte(fecha, periodo="dia"):
    periodo = periodo if periodo in PERIODOS else "dia"
    desde, hasta = rango(fecha, periodo)
    pedidos = _pedidos_entre(desde, hasta)
    validos = [p for p in pedidos if p.estado != "cancelado"]
    pagados = [(p, _pago(p)) for p in validos if _pago(p)]
    total = sum(pago.monto for _, pago in pagados)
    en_app = sum(1 for _, pago in pagados if pago.metodo == "app")

    # mismo periodo inmediatamente anterior, para comparar
    antes = rango(desde - timedelta(days=1), periodo)
    anterior = _total(_pedidos_entre(*antes))

    vendidos = Counter()
    for p, _ in pagados:
        for d in p.detalles:
            vendidos[d.producto.nombre] += d.subtotal

    return {
        "periodo": periodo,
        "desde": desde,
        "hasta": hasta,
        "total": total,
        "anterior": anterior,
        "variacion": round((total - anterior) / anterior * 100) if anterior else None,
        "pedidos": len(validos),
        "qr": sum(1 for p in validos if p.origen == "qr"),
        "presenciales": sum(1 for p in validos if p.origen == "presencial"),
        "cancelados": len(pedidos) - len(validos),
        "pagados": len(pagados),
        "en_app": en_app,
        "en_efectivo": len(pagados) - en_app,
        "pct_app": round(en_app / len(pagados) * 100) if pagados else 0,
        "ticket": total / len(pagados) if pagados else 0,
        "barras": _barras(pagados, periodo, desde, hasta),
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


def inventario(buscar="", categoria="", estado=""):
    productos = (Producto.query.join(Categoria)
                 .order_by(Categoria.nombre, Producto.nombre).all())
    buscar = buscar.strip().lower()
    if buscar:
        productos = [p for p in productos if buscar in p.nombre.lower()]
    if categoria:
        productos = [p for p in productos if p.categoria.nombre == categoria]
    if estado:
        productos = [p for p in productos if estado_producto(p) == estado]
    return productos


def ventas_producto(id_producto):
    return DetallePedido.query.filter_by(id_producto=id_producto).count()


@reintentar
def eliminar_producto(id_producto):
    # si ya se vendio no se borra: los pedidos y reportes lo necesitan
    with transaccion("eliminar_producto"):
        p = db.session.get(Producto, id_producto)
        if p is None:
            raise ErrorNegocio("Producto no encontrado", "El producto ya no existe.")
        ventas = ventas_producto(p.id_producto)
        if ventas:
            raise ErrorNegocio("No se puede eliminar",
                               f"{p.nombre} aparece en {ventas} pedido(s) y se necesita para el historial "
                               "y los reportes. Desactívalo para sacarlo del menú.")
        nombre = p.nombre
        db.session.delete(p)
        return nombre


@reintentar
def entrada_stock(id_producto, cantidad):
    cantidad = _entero(cantidad, "La cantidad", 1, MAX_ENTRADA)
    with transaccion("entrada_stock"):
        p = db.session.get(Producto, id_producto)
        if p is None:
            raise ErrorNegocio("Producto no encontrado", "El producto ya no existe.")
        if p.stock_actual + cantidad > MAX_STOCK:
            raise ErrorNegocio("Cantidad no válida",
                               f"{p.nombre} quedaría con más de {MAX_STOCK} unidades. Revisa la cantidad.")
        p.stock_actual += cantidad
        return p.nombre, p.stock_actual


@reintentar
def guardar_producto(datos, id_producto=None):
    nombre = " ".join(datos.get("nombre", "").split())
    categoria = " ".join(datos.get("categoria", "").split())
    descripcion = " ".join(datos.get("descripcion", "").split())
    if not 2 <= len(nombre) <= 60:
        raise ErrorNegocio("Datos no válidos", "El nombre del producto debe tener entre 2 y 60 caracteres.")
    if limpiar_nombre(categoria) is None or len(categoria) > 30:
        raise ErrorNegocio("Datos no válidos", "La categoría debe tener solo letras (2 a 30 caracteres).")
    if len(descripcion) > 80:
        raise ErrorNegocio("Datos no válidos", "La descripción puede tener máximo 80 caracteres.")
    precio = _entero(datos.get("precio"), "El precio", 50, 500000)
    if precio % 50:
        raise ErrorNegocio("Datos no válidos", "El precio debe ir de 50 en 50 pesos (por ejemplo 2.500 o 2.550).")
    stock = _entero(datos.get("stock_actual"), "El stock actual", 0, MAX_STOCK)
    minimo = _entero(datos.get("stock_minimo"), "El stock mínimo", 0, MAX_STOCK)

    with transaccion("guardar_producto"):
        repetido = Producto.query.filter(func.lower(Producto.nombre) == nombre.lower(),
                                         Producto.id_producto != (id_producto or 0)).first()
        if repetido:
            raise ErrorNegocio("Producto repetido", f"Ya existe un producto llamado {repetido.nombre}.")
        cat = Categoria.query.filter(func.lower(Categoria.nombre) == categoria.lower()).first()
        if cat is None:
            cat = Categoria(nombre=categoria)
            db.session.add(cat)
        p = db.session.get(Producto, id_producto) if id_producto else Producto()
        if p is None:
            raise ErrorNegocio("Producto no encontrado", "El producto ya no existe.")
        p.nombre, p.descripcion, p.precio = nombre, descripcion or None, precio
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


def _validar_clave(clave):
    if not 8 <= len(clave) <= 64:
        raise ErrorNegocio("Contraseña no válida", "La contraseña debe tener entre 8 y 64 caracteres.")


def _datos_usuario(nombre, username, rol):
    nombre, username = limpiar_nombre(nombre), (username or "").strip().lower()
    if nombre is None:
        raise ErrorNegocio("Nombre no válido", "El nombre solo puede tener letras y espacios (2 a 60 caracteres).")
    if not USUARIO.match(username):
        raise ErrorNegocio("Usuario no válido", "El usuario debe tener de 3 a 20 letras, números o puntos, sin espacios.")
    if rol not in ("cajero", "administrador"):
        raise ErrorNegocio("Faltan datos", "Elige el rol del usuario.")
    return nombre, username


def usuarios(buscar="", rol="", estado=""):
    lista = Usuario.query.order_by(Usuario.activo.desc(), Usuario.nombre).all()
    buscar = buscar.strip().lower()
    if buscar:
        lista = [u for u in lista if buscar in u.nombre.lower() or buscar in u.username]
    if rol:
        lista = [u for u in lista if u.rol == rol]
    if estado:
        lista = [u for u in lista if u.activo == (estado == "activo")]
    return lista


@reintentar
def editar_usuario(id_usuario, nombre, username, rol, activo, quien):
    nombre, username = _datos_usuario(nombre, username, rol)
    with transaccion("editar_usuario"):
        u = db.session.get(Usuario, id_usuario)
        if u is None:
            raise ErrorNegocio("Usuario no encontrado", "El usuario ya no existe.")
        if u.id_usuario == quien.id_usuario and (rol != u.rol or not activo):
            raise ErrorNegocio("No permitido", "No puedes cambiar tu propio rol ni desactivar tu usuario.")
        otro = Usuario.query.filter(Usuario.username == username, Usuario.id_usuario != u.id_usuario).first()
        if otro:
            raise ErrorNegocio("Usuario repetido", f"Ya existe el usuario {username}.")
        u.nombre, u.username, u.rol, u.activo = nombre, username, rol, activo
        return u.username


def registros_usuario(id_usuario):
    return (Pedido.query.filter_by(id_usuario=id_usuario).count()
            + Pago.query.filter_by(id_usuario=id_usuario).count()
            + Transaccion.query.filter_by(id_usuario=id_usuario).count())


@reintentar
def eliminar_usuario(id_usuario, quien):
    # quien ya atendio pedidos o cobro queda en el historial, por eso solo se desactiva
    with transaccion("eliminar_usuario"):
        u = db.session.get(Usuario, id_usuario)
        if u is None:
            raise ErrorNegocio("Usuario no encontrado", "El usuario ya no existe.")
        if u.id_usuario == quien.id_usuario:
            raise ErrorNegocio("No permitido", "No puedes eliminar tu propio usuario.")
        registros = registros_usuario(u.id_usuario)
        if registros:
            raise ErrorNegocio("No se puede eliminar",
                               f"{u.username} tiene {registros} registro(s) de pedidos, pagos o transacciones "
                               "a su nombre. Desactívalo para quitarle el acceso sin perder el historial.")
        nombre = u.username
        db.session.delete(u)
        return nombre


@reintentar
def crear_usuario(nombre, username, rol, clave):
    nombre, username = _datos_usuario(nombre, username, rol)
    _validar_clave(clave)
    with transaccion("crear_usuario"):
        if Usuario.query.filter_by(username=username).first():
            raise ErrorNegocio("Usuario repetido", f"Ya existe el usuario {username}.")
        db.session.add(Usuario(nombre=nombre, username=username, rol=rol,
                               password_hash=generate_password_hash(clave)))


def cambiar_clave(id_usuario, clave):
    _validar_clave(clave)
    with transaccion("cambiar_clave"):
        u = db.session.get(Usuario, id_usuario)
        if u is None:
            raise ErrorNegocio("Usuario no encontrado", "El usuario ya no existe.")
        u.password_hash = generate_password_hash(clave)
        return u.username


def hoy():
    return ahora().date()
