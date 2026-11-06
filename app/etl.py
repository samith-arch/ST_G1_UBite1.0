# proceso ETL: lleva las ventas de ubite.db al almacen ubite_dw.db y exporta los datasets
# que usan Power BI y la red neuronal.
#
#   flask --app run etl              carga lo nuevo hasta ayer
#   flask --app run etl --completo   borra el almacen y lo vuelve a cargar desde cero
import hashlib
import hmac
import os
import sqlite3
from datetime import date, datetime, timedelta

import click
import pandas as pd

from . import calendario
from .database import DB_PATH

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DW_PATH = os.environ.get("UBITE_DW", os.path.join(RAIZ, "database", "ubite_dw.db"))
ESQUEMA = os.path.join(RAIZ, "database", "almacen.sql")
SALIDA = os.path.join(RAIZ, "ia", "datos")
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
FRANJAS_ATENCION = range(14, 38)     # de 7:00 a 18:30
TABLAS = ("hecho_venta", "hecho_pedido", "hecho_inventario", "prediccion_demanda",
          "etl_control", "dim_producto", "dim_franja", "dim_fecha")


def anonimo(telefono, clave):
    # HMAC-SHA256 del celular: el mismo cliente siempre da el mismo codigo, pero no se puede
    # volver al numero sin la clave del .env
    return hmac.new(clave.encode(), str(telefono).encode(), hashlib.sha256).hexdigest()[:16]


def _id_fecha(serie):
    return serie.dt.strftime("%Y%m%d").astype(int)


def _id_franja(serie):
    return serie.dt.hour * 2 + (serie.dt.minute >= 30).astype(int)


def _extraer(origen, desde, hasta):
    q = lambda sql, *p: pd.read_sql_query(sql, origen, params=p)
    pedidos = q("""SELECT p.id_pedido, p.fecha_hora, p.origen, p.estado, p.total, c.telefono
                   FROM pedido p JOIN cliente c USING (id_cliente)
                   WHERE date(p.fecha_hora) > ? AND date(p.fecha_hora) <= ?""", desde, hasta)
    ids = pedidos["id_pedido"].tolist() or [0]
    marcas = ",".join("?" * len(ids))
    detalles = q(f"SELECT id_pedido, id_producto, cantidad, subtotal FROM detalle_pedido WHERE id_pedido IN ({marcas})", *ids)
    pagos = q(f"SELECT id_pedido, metodo FROM pago WHERE estado = 'aprobado' AND id_pedido IN ({marcas})", *ids)
    tiempos = q(f"""SELECT id_pedido,
                       MIN(CASE WHEN descripcion LIKE '%-> listo%' THEN fecha_hora END) AS listo,
                       MIN(CASE WHEN descripcion LIKE '%listo -> entregado%' THEN fecha_hora END) AS entregado
                    FROM transaccion WHERE id_pedido IN ({marcas}) GROUP BY id_pedido""", *ids)
    productos = q("""SELECT p.id_producto, p.nombre, c.nombre AS categoria, p.precio AS precio_actual,
                            p.activo, p.stock_actual, p.stock_minimo
                     FROM producto p JOIN categoria c USING (id_categoria)""")
    return pedidos, detalles, pagos, tiempos, productos


def _transformar(pedidos, detalles, pagos, tiempos, clave):
    pedidos = pedidos.copy()
    pedidos["fecha_hora"] = pd.to_datetime(pedidos["fecha_hora"], format="mixed")

    # se descartan los pedidos todavia abiertos y los que tienen el total descuadrado
    abiertos = ~pedidos["estado"].isin(["entregado", "cancelado"])
    suma = detalles.groupby("id_pedido")["subtotal"].sum()
    descuadrados = (pedidos["total"] - pedidos["id_pedido"].map(suma).fillna(0)).abs() > 0.5
    rechazados = {"abiertos": int(abiertos.sum()), "descuadrados": int((descuadrados & ~abiertos).sum())}
    pedidos = pedidos[~abiertos & ~descuadrados]

    pedidos = pedidos.merge(pagos.drop_duplicates("id_pedido"), on="id_pedido", how="left")
    pedidos = pedidos.merge(tiempos, on="id_pedido", how="left")
    for col in ("listo", "entregado"):
        pedidos[col] = pd.to_datetime(pedidos[col], format="mixed")
    pedidos["id_fecha"] = _id_fecha(pedidos["fecha_hora"])
    pedidos["id_franja"] = _id_franja(pedidos["fecha_hora"])
    pedidos["cliente_anonimo"] = pedidos["telefono"].map(lambda t: anonimo(t, clave))

    hecho_pedido = pd.DataFrame({
        "id_pedido": pedidos["id_pedido"], "id_fecha": pedidos["id_fecha"], "id_franja": pedidos["id_franja"],
        "cliente_anonimo": pedidos["cliente_anonimo"], "origen": pedidos["origen"],
        "metodo_pago": pedidos["metodo"], "estado_final": pedidos["estado"],
        "min_cola_a_listo": ((pedidos["listo"] - pedidos["fecha_hora"]).dt.total_seconds() / 60).round(1),
        "min_listo_a_entrega": ((pedidos["entregado"] - pedidos["listo"]).dt.total_seconds() / 60).round(1),
        "total": pedidos["total"]})

 
    entregados = pedidos[pedidos["estado"] == "entregado"][["id_pedido", "id_fecha", "id_franja", "origen", "metodo"]]
    hecho_venta = detalles.merge(entregados, on="id_pedido").rename(columns={"metodo": "metodo_pago", "subtotal": "valor"})
    hecho_venta = hecho_venta[["id_pedido", "id_fecha", "id_franja", "id_producto", "origen", "metodo_pago", "cantidad", "valor"]]
    return hecho_pedido, hecho_venta, rechazados


def _dim_fecha(desde, hasta):
    filas, dia = [], desde
    while dia <= hasta:
        filas.append((int(dia.strftime("%Y%m%d")), dia.isoformat(), dia.weekday(), DIAS[dia.weekday()],
                      calendario.semana_semestre(dia), calendario.periodo(dia), int(dia in calendario.FESTIVOS)))
        dia += timedelta(days=1)
    return filas


def _cargar(dw, hecho_pedido, hecho_venta, productos, desde, hasta, hoy, vendido_hoy):
    nulos = lambda df: [tuple(None if pd.isna(v) else v for v in fila) for fila in df.itertuples(index=False)]
    with dw:     # una sola transaccion: si algo falla no queda nada a medias
        dw.executemany("INSERT OR IGNORE INTO dim_franja VALUES (?, ?, ?)",
                       [(i, f"{i // 2:02d}:{30 * (i % 2):02d}", f"{(i + 1) // 2 % 24:02d}:{30 * ((i + 1) % 2):02d}")
                        for i in range(48)])
        dw.executemany("INSERT OR REPLACE INTO dim_fecha VALUES (?, ?, ?, ?, ?, ?, ?)", _dim_fecha(desde, hoy))
        dw.executemany("INSERT OR REPLACE INTO dim_producto VALUES (?, ?, ?, ?, ?)",
                       nulos(productos[["id_producto", "nombre", "categoria", "precio_actual", "activo"]]))
        dw.executemany("INSERT OR IGNORE INTO hecho_pedido VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", nulos(hecho_pedido))
        antes = dw.total_changes
        dw.executemany("INSERT INTO hecho_venta (id_pedido, id_fecha, id_franja, id_producto, origen, metodo_pago, cantidad, valor) "
                       "SELECT ?, ?, ?, ?, ?, ?, ?, ? WHERE NOT EXISTS "
                       "(SELECT 1 FROM hecho_venta WHERE id_pedido = ? AND id_producto = ?)",
                       [f + (f[0], f[3]) for f in nulos(hecho_venta)])
        ventas = dw.total_changes - antes
        id_hoy = int(hoy.strftime("%Y%m%d"))
        dw.executemany("INSERT OR REPLACE INTO hecho_inventario VALUES (?, ?, ?, ?, ?)",
                       [(id_hoy, int(r.id_producto), int(r.stock_actual), int(r.stock_minimo),
                         int(vendido_hoy.get(r.id_producto, 0))) for r in productos.itertuples()])
        return ventas


def _exportar(dw):
    os.makedirs(SALIDA, exist_ok=True)
    ventas = pd.read_sql_query("""
        SELECT f.fecha, f.nombre_dia, f.periodo, fr.hora_inicio AS franja, v.id_producto, p.nombre AS producto,
               p.categoria, v.cantidad, v.valor, v.origen, v.metodo_pago, hp.cliente_anonimo
        FROM hecho_venta v JOIN dim_fecha f USING (id_fecha) JOIN dim_franja fr USING (id_franja)
        JOIN dim_producto p USING (id_producto) JOIN hecho_pedido hp USING (id_pedido)
        ORDER BY f.fecha, fr.hora_inicio""", dw)
    ventas.to_csv(os.path.join(SALIDA, "dataset_ventas.csv"), index=False, encoding="utf-8")

    agregado = pd.read_sql_query("SELECT id_fecha, id_franja, id_producto, SUM(cantidad) AS unidades "
                                 "FROM hecho_venta GROUP BY 1, 2, 3", dw)
    dias = pd.read_sql_query("SELECT f.* FROM dim_fecha f WHERE id_fecha IN (SELECT DISTINCT id_fecha FROM hecho_pedido)", dw)
    productos = pd.read_sql_query("SELECT id_producto, nombre AS producto, categoria FROM dim_producto", dw)
    franjas = pd.DataFrame({"id_franja": list(FRANJAS_ATENCION)})
    tabla = dias.merge(franjas, how="cross").merge(productos, how="cross")
    tabla = tabla.merge(agregado, on=["id_fecha", "id_franja", "id_producto"], how="left")
    tabla["unidades"] = tabla["unidades"].fillna(0).astype(int)

    tabla["fecha"] = pd.to_datetime(tabla["fecha"])
    previa = tabla[["fecha", "id_franja", "id_producto", "unidades"]].copy()
    previa["fecha"] = previa["fecha"] + pd.Timedelta(days=7)
    tabla = tabla.merge(previa.rename(columns={"unidades": "ventas_semana_anterior"}),
                        on=["fecha", "id_franja", "id_producto"], how="left")
    tabla["ventas_semana_anterior"] = tabla["ventas_semana_anterior"].fillna(0).astype(int)
    tabla["examenes"] = tabla["periodo"].isin(["parciales", "finales"]).astype(int)
    tabla["fecha"] = tabla["fecha"].dt.date
    columnas = ["fecha", "dia_semana", "nombre_dia", "periodo", "examenes", "es_festivo", "id_franja",
                "id_producto", "producto", "categoria", "ventas_semana_anterior", "unidades"]
    tabla[columnas].sort_values(["fecha", "id_franja", "id_producto"]).to_csv(
        os.path.join(SALIDA, "dataset_demanda.csv"), index=False, encoding="utf-8")
    return len(ventas), len(tabla)


def ejecutar(completo=False):
    clave = os.environ.get("UBITE_CLAVE_ANONIMA")
    if not clave:
        raise click.ClickException("Falta UBITE_CLAVE_ANONIMA en el .env (ver .env.example).")
    if not os.path.exists(DB_PATH):
        raise click.ClickException(f"No existe {DB_PATH}. Corre primero database/crear_bd.py")

    dw = sqlite3.connect(DW_PATH)
    dw.execute("PRAGMA foreign_keys = ON")
    if completo:
        with dw:
            for t in TABLAS:
                dw.execute(f"DROP TABLE IF EXISTS {t}")
    with open(ESQUEMA, encoding="utf-8") as f:
        dw.executescript(f.read())

    hoy = date.today()
    ultima = dw.execute("SELECT MAX(ultima_fecha_extraida) FROM etl_control WHERE resultado = 'ok'").fetchone()[0]
    # se repasan los ultimos 3 dias por si quedo algun pedido abierto
    desde = date.fromisoformat(ultima) - timedelta(days=3) if ultima else date(2000, 1, 1)
    hasta = hoy - timedelta(days=1)          # el dia de hoy todavia no ha cerrado

    # la base transaccional se abre en solo lectura
    origen = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        pedidos, detalles, pagos, tiempos, productos = _extraer(origen, desde.isoformat(), hasta.isoformat())
        vendido_hoy = pd.read_sql_query(
            "SELECT d.id_producto, SUM(d.cantidad) AS n FROM detalle_pedido d JOIN pedido p USING (id_pedido) "
            "WHERE p.estado = 'entregado' AND date(p.fecha_hora) = ? GROUP BY 1", origen,
            params=(hoy.isoformat(),)).set_index("id_producto")["n"].to_dict()
    finally:
        origen.close()

    try:
        hecho_pedido, hecho_venta, rechazados = _transformar(pedidos, detalles, pagos, tiempos, clave)
        inicio = pd.to_datetime(pedidos["fecha_hora"], format="mixed").min().date() if len(pedidos) else hasta
        primero = dw.execute("SELECT MIN(fecha) FROM dim_fecha").fetchone()[0]
        inicio = min(inicio, date.fromisoformat(primero)) if primero else inicio
        ventas = _cargar(dw, hecho_pedido, hecho_venta, productos, inicio, hasta, hoy, vendido_hoy)
        detalle = (f"{len(hecho_pedido)} pedidos; omitidos {rechazados['abiertos']} sin cerrar "
                   f"y {rechazados['descuadrados']} con total descuadrado")
        with dw:
            dw.execute("INSERT INTO etl_control (fecha_ejecucion, ultima_fecha_extraida, filas_cargadas, resultado, detalle) "
                       "VALUES (?, ?, ?, 'ok', ?)", (datetime.now().isoformat(" ", "seconds"), hasta.isoformat(),
                                                    len(hecho_pedido) + ventas, detalle))
    except Exception as e:
        with dw:
            dw.execute("INSERT INTO etl_control (fecha_ejecucion, ultima_fecha_extraida, filas_cargadas, resultado, detalle) "
                       "VALUES (?, ?, 0, 'error', ?)", (datetime.now().isoformat(" ", "seconds"), ultima, str(e)[:300]))
        dw.close()
        raise click.ClickException(f"El ETL falló y no se cargó nada: {e}")

    filas_ventas, filas_demanda = _exportar(dw)
    dw.close()
    return {"pedidos": len(hecho_pedido), "ventas": ventas, "detalle": detalle,
            "dataset_ventas": filas_ventas, "dataset_demanda": filas_demanda, "hasta": hasta}


def registrar(app):
    @app.cli.command("etl")
    @click.option("--completo", is_flag=True, help="Borra el almacén y lo carga desde cero.")
    def etl(completo):
        """Carga el almacén de datos y exporta los datasets."""
        r = ejecutar(completo)
        click.echo(f"ETL hasta {r['hasta']}: {r['pedidos']} pedidos y {r['ventas']} líneas de venta nuevas ({r['detalle']}).")
        click.echo(f"Datasets en ia/datos: dataset_ventas.csv ({r['dataset_ventas']} filas) "
                   f"y dataset_demanda.csv ({r['dataset_demanda']} filas).")
