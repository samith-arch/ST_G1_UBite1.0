# entrena la red neuronal que estima las unidades vendidas por producto y franja.
#
#   python entrenar_modelo.py
#
# lee datos/dataset_demanda.csv (lo genera "flask etl"), entrena con todas las semanas menos
# las dos ultimas, prueba con esas dos y compara contra el promedio historico de la franja.
# guarda el modelo en modelo/ y las estimaciones de manana en la tabla prediccion_demanda.
import json
import os
import sqlite3
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import tensorflow as tf

import ia.demanda as d

SEMILLA = 42
DIAS_PRUEBA = 14
SEMANAS_REFERENCIA = 4


def cargar():
    if not os.path.exists(d.DATASET):
        raise SystemExit(f"No existe {d.DATASET}. En la carpeta del proyecto corre: flask --app run etl")
    datos = pd.read_csv(d.DATASET, parse_dates=["fecha"])
    datos = datos[datos["dia_semana"] < d.DIAS_ABIERTOS].copy()
    datos["periodo_red"] = datos["periodo"].map(d.periodo_red)
    return datos


def separar(datos):
    dias = sorted(datos["fecha"].unique())
    corte = dias[-DIAS_PRUEBA]
    return datos[datos["fecha"] < corte], datos[datos["fecha"] >= corte], pd.Timestamp(corte).date()


def matriz(tabla, meta):
    return d.entradas(tabla["id_producto"], tabla["dia_semana"], tabla["id_franja"],
                      tabla["periodo_red"], tabla["ventas_semana_anterior"], meta)


def construir(n_entradas):
    # la misma red del documento: entrada, una capa oculta de 8 neuronas con ReLU y una salida lineal
    modelo = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(n_entradas,)),
        tf.keras.layers.Dense(8, activation="relu", name="capa_oculta"),
        tf.keras.layers.Dense(1, activation="linear", name="salida"),
    ])
    modelo.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.005), loss="mse", metrics=["mae"])
    return modelo


def guardar_predicciones(modelo, meta, datos, usar, referencia):
    dia = datos["fecha"].max().date() + timedelta(days=1)
    while not d.abierto(dia):
        dia += timedelta(days=1)
    franjas = list(range(d.PRIMERA_FRANJA, d.ULTIMA_FRANJA + 1))
    tabla = pd.DataFrame([(p, f) for p in meta["productos"] for f in franjas], columns=["id_producto", "id_franja"])
    tabla["dia_semana"] = dia.weekday()
    tabla["periodo_red"] = d.periodo_de(dia)
    previa = datos[datos["fecha"] == pd.Timestamp(dia - timedelta(days=7))][["id_producto", "id_franja", "unidades"]]
    tabla = tabla.merge(previa.rename(columns={"unidades": "ventas_semana_anterior"}), how="left",
                        on=["id_producto", "id_franja"])
    tabla["ventas_semana_anterior"] = tabla["ventas_semana_anterior"].fillna(0)
    if usar == "red_neuronal":
        estimado = modelo.predict(matriz(tabla, meta), verbose=0).ravel()
    else:
        estimado = tabla.merge(referencia, how="left", on=["id_producto", "dia_semana", "id_franja"])["promedio"].fillna(0).to_numpy()
    tabla["unidades_estimadas"] = np.clip(estimado, 0, None).round(2)

    if not os.path.exists(d.DW):
        print("No se encontró ubite_dw.db; las predicciones no se guardaron en el almacén.")
        return dia, 0
    id_fecha = int(dia.strftime("%Y%m%d"))
    ahora = datetime.now().isoformat(" ", "seconds")
    con = sqlite3.connect(d.DW)
    try:
        with con:     
            con.execute("INSERT OR IGNORE INTO dim_fecha VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (id_fecha, dia.isoformat(), dia.weekday(), ["lunes", "martes", "miércoles", "jueves",
                         "viernes", "sábado", "domingo"][dia.weekday()], d.calendario.semana_semestre(dia),
                         d.calendario.periodo(dia), int(dia in d.calendario.FESTIVOS)))
            con.execute("DELETE FROM prediccion_demanda WHERE id_fecha = ?", (id_fecha,))
            con.executemany("INSERT INTO prediccion_demanda VALUES (?, ?, ?, ?, ?, ?)",
                            [(id_fecha, int(r.id_franja), int(r.id_producto), float(r.unidades_estimadas), usar, ahora)
                             for r in tabla.itertuples()])
    finally:
        con.close()
    return dia, len(tabla)


def main():
    tf.keras.utils.set_random_seed(SEMILLA)
    datos = cargar()
    entreno, prueba, corte = separar(datos)
    meta = {"productos": sorted(int(p) for p in datos["id_producto"].unique()),
            "nombres": datos.drop_duplicates("id_producto").set_index("id_producto")["producto"].to_dict(),
            "max_semana_anterior": float(max(entreno["ventas_semana_anterior"].max(), 1))}
    meta["nombres"] = {int(k): v for k, v in meta["nombres"].items()}

    x_entreno, y_entreno = matriz(entreno, meta), entreno["unidades"].to_numpy(np.float32)
    x_prueba, y_prueba = matriz(prueba, meta), prueba["unidades"].to_numpy(np.float32)
    print(f"Entrenamiento: {len(entreno)} filas hasta {corte - timedelta(days=1)} | prueba: {len(prueba)} filas desde {corte}")
    print(f"Capa de entrada: {x_entreno.shape[1]} valores")

    modelo = construir(x_entreno.shape[1])
    parar = tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=3, restore_best_weights=True)
    historia = modelo.fit(x_entreno, y_entreno, validation_split=0.1, epochs=40, batch_size=256,
                          callbacks=[parar], verbose=2)

    recientes = entreno[entreno["fecha"] >= pd.Timestamp(corte - timedelta(weeks=SEMANAS_REFERENCIA))]
    referencia = (recientes.groupby(["id_producto", "dia_semana", "id_franja"])["unidades"].mean()
                  .rename("promedio").reset_index())
    con_ref = prueba.merge(referencia, how="left", on=["id_producto", "dia_semana", "id_franja"])
    mae_ref = float(np.mean(np.abs(con_ref["promedio"].fillna(0) - con_ref["unidades"])))
    estimado = np.clip(modelo.predict(x_prueba, verbose=0).ravel(), 0, None)
    mae_red = float(np.mean(np.abs(estimado - y_prueba)))
    usar = "red_neuronal" if mae_red <= mae_ref else "referencia"

    prueba = prueba.assign(red=estimado, ref=con_ref["promedio"].fillna(0).to_numpy())
    por_dia = prueba.groupby(["fecha", "id_producto"])[["unidades", "red", "ref"]].sum()
    mae_dia_red = float(np.mean(np.abs(por_dia["red"] - por_dia["unidades"])))
    mae_dia_ref = float(np.mean(np.abs(por_dia["ref"] - por_dia["unidades"])))

    os.makedirs(os.path.dirname(d.MODELO), exist_ok=True)
    modelo.save(d.MODELO)
    referencia.to_csv(d.REFERENCIA, index=False)
    meta.update({
        "entrenado": datetime.now().isoformat(" ", "seconds"),
        "filas_entrenamiento": len(entreno), "filas_prueba": len(prueba),
        "prueba_desde": corte.isoformat(), "epocas": len(historia.history["loss"]),
        "mae_red_franja": round(mae_red, 4), "mae_referencia_franja": round(mae_ref, 4),
        "mae_red_dia": round(mae_dia_red, 3), "mae_referencia_dia": round(mae_dia_ref, 3),
        "usar": usar,
    })
    with open(d.METADATOS, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\nError absoluto medio por franja: red {mae_red:.3f} | referencia {mae_ref:.3f}")
    print(f"Error absoluto medio por producto en el día: red {mae_dia_red:.2f} | referencia {mae_dia_ref:.2f} unidades")
    print(f"Se usará: {usar}. Modelo guardado en {d.MODELO}")
    dia, filas = guardar_predicciones(modelo, meta, datos, usar, referencia)
    if filas:
        print(f"Predicciones del {dia} guardadas en prediccion_demanda ({filas} filas).")


if __name__ == "__main__":
    main()
