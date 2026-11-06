# servicio web de la red neuronal de UBite.
#
#   uvicorn api:app --port 8000
#
# y en el navegador http://127.0.0.1:8000/docs para probarlo.
import json
import os
import sqlite3
from datetime import date, timedelta

import numpy as np
import pandas as pd
import tensorflow as tf
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

import demanda as d

if not os.path.exists(d.MODELO):
    raise SystemExit("No hay modelo entrenado. Corre primero: python entrenar_modelo.py")
modelo = tf.keras.models.load_model(d.MODELO)
with open(d.METADATOS, encoding="utf-8") as f:
    meta = json.load(f)
meta["nombres"] = {int(k): v for k, v in meta["nombres"].items()}
referencia = pd.read_csv(d.REFERENCIA)

app = FastAPI(title="UBite · servicio de demanda",
              description="Estima cuántas unidades de cada producto se venderán por franja de 30 minutos "
                          "y avisa qué productos se agotarían con el stock actual.",
              version="1.0.0")

HORA = r"^([01]\d|2[0-3]):(00|30)$"


class Consulta(BaseModel):
    fecha: date = Field(description="Día que se quiere estimar")
    id_producto: int = Field(ge=1, description="Producto del inventario de UBite")
    desde: str = Field("07:00", pattern=HORA, description="Primera franja, en bloques de 30 minutos")
    hasta: str = Field("18:30", pattern=HORA, description="Última franja")

    @field_validator("fecha")
    @classmethod
    def fecha_cercana(cls, v):
        if abs((v - date.today()).days) > 60:
            raise ValueError("solo se estiman fechas de 60 días atrás a 60 días adelante")
        return v


class ConsultaAlertas(BaseModel):
    fecha: date = Field(description="Día que se quiere revisar")
    desde: str = Field("07:00", pattern=HORA, description="Desde qué franja contar (por ejemplo la actual)")
    stock: dict[int, int] = Field(description="Stock actual de cada producto: {id_producto: unidades}",
                                  examples=[{"7": 12, "1": 30, "5": 3}])

    @field_validator("stock")
    @classmethod
    def stock_valido(cls, v):
        if not v:
            raise ValueError("envía al menos un producto")
        if any(u < 0 for u in v.values()):
            raise ValueError("el stock no puede ser negativo")
        return v


def _franjas(desde, hasta):
    a, b = max(d.texto_a_franja(desde), d.PRIMERA_FRANJA), min(d.texto_a_franja(hasta), d.ULTIMA_FRANJA)
    if a > b:
        raise HTTPException(422, "La franja de inicio debe ser anterior a la final y estar entre 07:00 y 18:30.")
    return list(range(a, b + 1))


def _semana_anterior(fecha, productos, franjas):
    # ventas de la misma franja siete dias antes, leidas del almacen en solo lectura
    if not os.path.exists(d.DW):
        return {}
    marcas = ",".join("?" * len(productos))
    con = sqlite3.connect(f"file:{d.DW}?mode=ro", uri=True)
    try:
        filas = con.execute(
            f"SELECT id_producto, id_franja, SUM(cantidad) FROM hecho_venta WHERE id_fecha = ? "
            f"AND id_producto IN ({marcas}) GROUP BY 1, 2",
            (int((fecha - timedelta(days=7)).strftime("%Y%m%d")), *productos)).fetchall()
    finally:
        con.close()
    return {(p, f): n for p, f, n in filas if f in franjas}


def estimar(fecha, productos, franjas):
    if not d.abierto(fecha):
        return np.zeros((len(productos), len(franjas)))
    previas = _semana_anterior(fecha, productos, franjas)
    pares = [(p, f) for p in productos for f in franjas]
    if meta["usar"] == "red_neuronal":
        x = d.entradas([p for p, _ in pares], [fecha.weekday()] * len(pares), [f for _, f in pares],
                       [d.periodo_de(fecha)] * len(pares), [previas.get(par, 0) for par in pares], meta)
        y = modelo.predict(x, verbose=0).ravel()
    else:
        tabla = pd.DataFrame(pares, columns=["id_producto", "id_franja"]).assign(dia_semana=fecha.weekday())
        y = tabla.merge(referencia, how="left", on=["id_producto", "dia_semana", "id_franja"])["promedio"].fillna(0).to_numpy()
    return np.clip(y, 0, None).reshape(len(productos), len(franjas))


def _revisar_productos(ids):
    desconocidos = [p for p in ids if p not in meta["nombres"]]
    if desconocidos:
        raise HTTPException(404, f"Productos que el modelo no conoce: {desconocidos}. Vuelve a correr el ETL y el entrenamiento.")


@app.get("/")
def inicio():
    return {"mensaje": "Servicio de demanda activo", "modelo": meta["usar"], "entrenado": meta["entrenado"],
            "error_medio_por_franja": {"red_neuronal": meta["mae_red_franja"], "referencia": meta["mae_referencia_franja"]}}


@app.post("/predecir")
def predecir(c: Consulta):
    _revisar_productos([c.id_producto])
    franjas = _franjas(c.desde, c.hasta)
    estimado = estimar(c.fecha, [c.id_producto], franjas)[0]
    return {
        "fecha": c.fecha, "id_producto": c.id_producto, "producto": meta["nombres"][c.id_producto],
        "abierto": d.abierto(c.fecha), "modelo": meta["usar"],
        "franjas": [{"franja": d.franja_a_texto(f), "unidades_estimadas": round(float(u), 2)}
                    for f, u in zip(franjas, estimado)],
        "total_estimado": round(float(estimado.sum()), 1),
        "nota": "Estimación entrenada con un historial simulado; sirve para validar el proceso, no para decisiones reales.",
    }


@app.post("/alertas")
def alertas(c: ConsultaAlertas):
    # los productos creados despues del ultimo entrenamiento se devuelven aparte
    ids = [p for p in c.stock if p in meta["nombres"]]
    sin_modelo = [p for p in c.stock if p not in meta["nombres"]]
    if not ids:
        _revisar_productos(sin_modelo)
    franjas = _franjas(c.desde, "18:30")
    totales = estimar(c.fecha, ids, franjas).sum(axis=1)
    productos = []
    for p, total in zip(ids, totales):
        faltan = max(0, int(np.ceil(total)) - c.stock[p])
        productos.append({"id_producto": p, "producto": meta["nombres"][p], "stock_actual": c.stock[p],
                          "estimado_resto_del_dia": round(float(total), 1), "se_agota": faltan > 0, "faltan": faltan})
    productos.sort(key=lambda x: (-x["faltan"], -x["estimado_resto_del_dia"]))
    return {"fecha": c.fecha, "desde": d.franja_a_texto(franjas[0]), "abierto": d.abierto(c.fecha),
            "modelo": meta["usar"], "productos": productos, "sin_modelo": sin_modelo}
