# plan B para Power BI si el controlador ODBC de SQLite da problemas:
# exporta las tablas del almacen a bi/tablas/*.csv para cargarlas con "Obtener datos > Texto/CSV".
#
#   python bi/exportar_tablas.py
import csv
import os
import sqlite3

CARPETA = os.path.dirname(os.path.abspath(__file__))
DW = os.environ.get("UBITE_DW", os.path.join(CARPETA, "..", "database", "ubite_dw.db"))
TABLAS = ["dim_fecha", "dim_franja", "dim_producto", "hecho_venta", "hecho_pedido",
          "hecho_inventario", "prediccion_demanda"]

if not os.path.exists(DW):
    raise SystemExit("No existe ubite_dw.db. Corre primero: flask --app run etl")
salida = os.path.join(CARPETA, "tablas")
os.makedirs(salida, exist_ok=True)
con = sqlite3.connect(f"file:{os.path.abspath(DW)}?mode=ro", uri=True)
try:
    for t in TABLAS:
        cur = con.execute(f"SELECT * FROM {t}")
        with open(os.path.join(salida, f"{t}.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow([c[0] for c in cur.description])
            n = 0
            for fila in cur:
                w.writerow([int(v) if isinstance(v, float) and v.is_integer() else v for v in fila])
                n += 1
        print(f"{t}: {n} filas")
finally:
    con.close()
