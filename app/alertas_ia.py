# consulta al servicio de IA (carpeta ia/) cuantas unidades se venderan en lo que queda del dia
# y lo compara con el stock real. Si el servicio esta apagado la app sigue funcionando normal.
import json
import math
import os
import time
import urllib.error
import urllib.request
from datetime import timedelta

from .calendario import FESTIVOS
from .models import Categoria, Producto, ahora

URL_IA = os.environ.get("UBITE_IA_URL", "http://127.0.0.1:8000")
APERTURA, CIERRE = (7, 0), (18, 30)


class ServicioNoDisponible(Exception):
    pass


# si el servicio no responde, no se vuelve a intentar durante un minuto para no frenar el inventario
_caido_hasta = 0


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


def _post(ruta, cuerpo, espera=8):
    global _caido_hasta
    if time.monotonic() < _caido_hasta:
        raise ServicioNoDisponible(None)
    peticion = urllib.request.Request(URL_IA + ruta, data=json.dumps(cuerpo).encode(),
                                      headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(peticion, timeout=espera) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            detalle = json.load(e).get("detail")
        except ValueError:
            detalle = None
        raise ServicioNoDisponible(detalle if isinstance(detalle, str) else f"El servicio respondió con error {e.code}.")
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        _caido_hasta = time.monotonic() + 60
        raise ServicioNoDisponible(None)


def siguiente_dia_abierto(dia):
    dia += timedelta(days=1)
    while not _abierto(dia):
        dia += timedelta(days=1)
    return dia


def alertas(espera=8, dia=None, desde=None, stock=None):
    productos = (Producto.query.join(Categoria).filter(Producto.activo.is_(True))
                 .order_by(Categoria.nombre, Producto.nombre).all())
    if dia is None:
        dia, desde = momento_consulta()
    stock = stock or {p.id_producto: p.stock_actual for p in productos}
    respuesta = _post("/alertas", {"fecha": dia.isoformat(), "desde": desde,
                                   "stock": {str(p.id_producto): stock[p.id_producto] for p in productos}},
                       espera)
    por_id = {p.id_producto: p for p in productos}
    filas = []
    for x in respuesta["productos"]:
        p = por_id[x["id_producto"]]
        filas.append({**x, "producto": p.nombre, "categoria": p.categoria.nombre, "precio": p.precio,
                      "minimo": p.stock_minimo, "bajo_minimo": p.stock_actual <= p.stock_minimo})
    return {"fecha": dia, "desde": desde, "modelo": respuesta["modelo"], "filas": filas,
            "agotan": sum(1 for f in filas if f["se_agota"]),
            "sin_modelo": [por_id[i].nombre for i in respuesta.get("sin_modelo", [])]}


TRASLADO = 0.5     # parte de los clientes de un agotado que se pasa a otro de la misma categoria


def con_sustitutos(productos, estimado):
    # si algo esta agotado, parte de lo que se iba a vender se reparte entre los de su categoria
    # que si tienen unidades, en proporcion a lo que ya vende cada uno
    extra, motivo = {}, {}
    activos = [p for p in productos if p.activo]
    for p in activos:
        e = estimado.get(p.id_producto)
        if p.stock_actual > 0 or not e or e["estimado_resto_del_dia"] < 1:
            continue
        otros = [o for o in activos if o.id_categoria == p.id_categoria and o.stock_actual > 0
                 and o.id_producto in estimado]
        base = sum(estimado[o.id_producto]["estimado_resto_del_dia"] for o in otros)
        for o in otros:
            parte = estimado[o.id_producto]["estimado_resto_del_dia"] / base if base else 1 / len(otros)
            extra[o.id_producto] = extra.get(o.id_producto, 0) + e["estimado_resto_del_dia"] * TRASLADO * parte
            motivo.setdefault(o.id_producto, []).append(p.nombre)
    return extra, motivo


def avisos_stock(productos, estimado):
    # junta en una lista lo que el inventario debe atender: agotados, los que la red
    # estima que se acaban antes del cierre (contando a los clientes de los agotados)
    # y los que ya estan en el minimo
    extra, motivo = con_sustitutos(productos, estimado)
    avisos = []
    for p in productos:
        if not p.activo:
            continue
        e = estimado.get(p.id_producto)
        if p.stock_actual == 0:
            a = p.agotamiento_abierto()
            aviso = {"p": p, "nivel": 0, "titulo": "Agotado", "agotamiento": a,
                     "texto": "No quedan unidades; en el menú aparece como agotado."}
            if a and a.sin_reposicion:
                aviso["titulo"] = "Agotado, no llega hoy"
                aviso["texto"] = (a.nota.rstrip(".") + ".") if a.nota else "Se marcó que hoy no se puede reponer."
            if e and e["estimado_resto_del_dia"] >= 1:
                perdidas = round(e["estimado_resto_del_dia"] * (1 - TRASLADO))
                plata = f"{perdidas * p.precio:,.0f}".replace(",", ".")
                aviso["texto"] += (f" La red estimaba {e['estimado_resto_del_dia']:.0f} ventas en lo que queda; "
                                   f"si la mitad compra otro producto, se pierden unas {perdidas} ($ {plata}).")
            avisos.append(aviso)
            continue
        if e:
            esperado = e["estimado_resto_del_dia"] + extra.get(p.id_producto, 0)
            faltan = max(0, math.ceil(esperado) - p.stock_actual)
            if faltan:
                texto = (f"La red estima {e['estimado_resto_del_dia']:.0f} ventas en lo que queda del día")
                if p.id_producto in extra and extra[p.id_producto] >= 0.5:
                    n = round(extra[p.id_producto])
                    agotados = motivo[p.id_producto]
                    texto += (f", {'una' if n == 1 else f'unas {n}'} más por los clientes de "
                              f"{', '.join(agotados)}, que {'está agotado' if len(agotados) == 1 else 'están agotados'}")
                texto += f". Hay {p.stock_actual}; faltarían {faltan}."
                avisos.append({"p": p, "nivel": 1, "titulo": "Se acabaría antes del cierre",
                               "texto": texto, "reponer": faltan})
                continue
        if p.stock_actual <= p.stock_minimo:
            avisos.append({"p": p, "nivel": 2, "titulo": "En el mínimo",
                           "texto": f"Quedan {p.stock_actual} y el mínimo es {p.stock_minimo}."})
    return sorted(avisos, key=lambda a: (a["nivel"], a["p"].nombre))


def para_manana(productos, hoy, espera=3):
    # lo que hay que pedir para el siguiente dia: stock que quedaria al cierre de hoy
    # contra lo que la red estima para todo ese dia
    dia = siguiente_dia_abierto(hoy["fecha"]) if hoy["fecha"] == ahora().date() else hoy["fecha"]
    if dia == hoy["fecha"]:
        quedaria = {p.id_producto: p.stock_actual for p in productos}
    else:
        vendido = {f["id_producto"]: f["estimado_resto_del_dia"] for f in hoy["filas"]}
        quedaria = {p.id_producto: max(0, p.stock_actual - math.ceil(vendido.get(p.id_producto, 0)))
                    for p in productos}
    manana = alertas(espera, dia, "07:00", quedaria)
    filas = [{**f, "quedaria": quedaria[f["id_producto"]], "pedir": f["faltan"]}
             for f in manana["filas"] if f["faltan"] > 0]
    return {"fecha": dia, "filas": sorted(filas, key=lambda f: -f["pedir"])}
