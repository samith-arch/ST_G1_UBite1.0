import importlib.util
import os

import numpy as np

CARPETA = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(CARPETA)
DATASET = os.path.join(CARPETA, "datos", "dataset_demanda.csv")
MODELO = os.path.join(CARPETA, "modelo", "modelo_demanda.keras")
METADATOS = os.path.join(CARPETA, "modelo", "metadatos.json")
REFERENCIA = os.path.join(CARPETA, "modelo", "referencia.csv")
DW = os.environ.get("UBITE_DW", os.path.join(RAIZ, "database", "ubite_dw.db"))

PRIMERA_FRANJA, ULTIMA_FRANJA = 14, 37      # 7:00 a 18:30, en bloques de 30 minutos
DIAS_ABIERTOS = 6                           # lunes a sabado

_spec = importlib.util.spec_from_file_location("calendario", os.path.join(RAIZ, "app", "calendario.py"))
calendario = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(calendario)


def franja_a_texto(id_franja):
    return f"{id_franja // 2:02d}:{30 * (id_franja % 2):02d}"


def texto_a_franja(texto):
    h, m = texto.split(":")
    return int(h) * 2 + (1 if int(m) >= 30 else 0)


def abierto(dia):
    return dia.weekday() < DIAS_ABIERTOS and dia not in calendario.FESTIVOS


PERIODOS = ["clases", "examenes", "semana santa", "intersemestral"]
AGRUPAR = {"parciales": "examenes", "finales": "examenes", "vacaciones": "intersemestral"}


def periodo_red(nombre):
    return PERIODOS.index(AGRUPAR.get(nombre, nombre))


def periodo_de(dia):
    return periodo_red(calendario.periodo(dia))


def entradas(productos, dia_semana, id_franja, periodo, semana_anterior, meta):
    productos = np.asarray(productos)
    n, base = len(productos), len(meta["productos"])
    franjas = ULTIMA_FRANJA - PRIMERA_FRANJA + 1
    x = np.zeros((n, base + DIAS_ABIERTOS + franjas + len(PERIODOS) + 1), dtype=np.float32)
    posicion = {p: i for i, p in enumerate(meta["productos"])}
    filas = np.arange(n)
    x[filas, [posicion[p] for p in productos]] = 1
    x[filas, base + np.asarray(dia_semana)] = 1
    x[filas, base + DIAS_ABIERTOS + np.asarray(id_franja) - PRIMERA_FRANJA] = 1
    x[filas, base + DIAS_ABIERTOS + franjas + np.asarray(periodo)] = 1
    x[:, -1] = np.asarray(semana_anterior) / meta["max_semana_anterior"]
    return x
