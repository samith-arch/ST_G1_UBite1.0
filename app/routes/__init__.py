from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def rol_requerido(*roles):
    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(*args, **kwargs):
            if current_user.rol not in roles:
                abort(403)
            return vista(*args, **kwargs)
        return envoltura
    return decorador


# ultima vez que cada usuario del personal hizo algo, para saber quien esta en linea
en_linea = {}


MENU_ADMIN = [
    ("admin.reporte", "Reporte", "bi-bar-chart"),
    ("caja.cola", "Pedidos en curso", "bi-grid"),
    ("caja.presencial", "Pedido presencial", "bi-bag"),
    ("inventario.lista", "Inventario", "bi-box-seam"),
    ("caja.historial", "Historial", "bi-clock-history"),
    ("admin.clientes", "Clientes", "bi-person-lines-fill"),
    ("admin.usuarios", "Usuarios", "bi-people"),
    ("admin.qr", "Código QR", "bi-qr-code"),
]
MENU_CAJERO = [
    ("caja.cola", "Pedidos en curso", "bi-grid"),
    ("caja.presencial", "Pedido presencial", "bi-bag"),
    ("inventario.lista", "Inventario", "bi-box-seam"),
    ("caja.historial", "Historial", "bi-clock-history"),
]
# en el celular solo caben cuatro, los demas del admin van en "Mas"
INFERIOR_ADMIN = [MENU_ADMIN[0], MENU_ADMIN[3], MENU_ADMIN[6], MENU_ADMIN[7]]
INFERIOR_CAJERO = [("caja.cola", "Pedidos", "bi-grid"), ("caja.presencial", "Presencial", "bi-bag"),
                   ("inventario.lista", "Inventario", "bi-box-seam"),
                   ("caja.historial", "Historial", "bi-clock-history")]


def datos_menu():
    if not current_user.is_authenticated:
        return {}
    from flask import request
    admin = current_user.rol == "administrador"
    seccion = request.endpoint
    if seccion in ("inventario.entrada", "inventario.producto"):
        seccion = "inventario.lista"
    return {"es_admin": admin, "seccion": seccion,
            "menu_personal": MENU_ADMIN if admin else MENU_CAJERO,
            "menu_inferior": INFERIOR_ADMIN if admin else INFERIOR_CAJERO}
