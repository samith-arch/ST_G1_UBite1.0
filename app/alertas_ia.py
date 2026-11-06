# consulta al servicio de IA (carpeta ia/) cuantas unidades se venderan en lo que queda del dia
# y lo compara con el stock real. Si el servicio esta apagado la app sigue funcionando normal.
import json
import os
import urllib.error
import urllib.request
from datetime import timedelta

from .calendario import FESTIVOS
from .models import Categoria, Producto, ahora

URL_IA = os.environ.get("UBITE_IA_URL", "http://127.0.0.1:8000")
APERTURA, CIERRE = (7, 0), (18, 30)


class ServicioNoDisponible(Exception):
    pass


def _abierto(dia):
    return dia.weekday() < 6 and dia not in FESTIVOS


def momento_consulta():
    t = ahora()
    dia, franja = t.date(), (t.hour, 0 if t.minute < 30 else 30)
    if franja < APERTURA:
        franja = APERTURA
    if franja > CIERRE or not _abierto(dia):
        dia, franja = dia + timedelta(days=1), APERTURA
        while not _abierto(dia):
            dia += timedelta(days=1)
    return dia, "%02d:%02d" % franja


def _post(ruta, cuerpo):
    peticion = urllib.request.Request(URL_IA + ruta, data=json.dumps(cuerpo).encode(),
                                      headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(peticion, timeout=8) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            detalle = json.load(e).get("detail")
        except ValueError:
            detalle = None
        raise ServicioNoDisponible(detalle if isinstance(detalle, str) else f"El servicio respondió con error {e.code}.")
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        raise ServicioNoDisponible(None)


def alertas():
    productos = (Producto.query.join(Categoria).filter(Producto.activo.is_(True))
                 .order_by(Categoria.nombre, Producto.nombre).all())
    dia, desde = momento_consulta()
    respuesta = _post("/alertas", {"fecha": dia.isoformat(), "desde": desde,
                                   "stock": {str(p.id_producto): p.stock_actual for p in productos}})
    por_id = {p.id_producto: p for p in productos}
    filas = []
    for x in respuesta["productos"]:
        p = por_id[x["id_producto"]]
        filas.append({**x, "producto": p.nombre, "categoria": p.categoria.nombre,
                      "minimo": p.stock_minimo, "bajo_minimo": p.stock_actual <= p.stock_minimo})
    return {"fecha": dia, "desde": desde, "modelo": respuesta["modelo"], "filas": filas,
            "agotan": sum(1 for f in filas if f["se_agota"]),
            "sin_modelo": [por_id[i].nombre for i in respuesta.get("sin_modelo", [])]}
