# crea database/ubite.db con schema.sql y datos_prueba.sql y la exporta a ubite.db.sql
# (mismo formato que "Export > Database to SQL file" de DB Browser)
#
#   python database/crear_bd.py             crea la base y la exporta
#   python database/crear_bd.py --exportar  solo exporta la base actual
import os
import secrets
import sqlite3
import sys
from datetime import datetime

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(os.path.dirname(DIR), ".env"))

# contraseña de cada usuario de prueba, se toma del .env
CLAVES = {"acajero": "UBITE_CLAVE_CAJERO", "admin": "UBITE_CLAVE_ADMIN"}
DB = os.path.join(DIR, "ubite.db")
EXPORT = os.path.join(DIR, "ubite.db.sql")

ORDEN = ["cliente", "usuario", "categoria", "producto", "pedido",
         "detalle_pedido", "pago", "transaccion", "notificacion"]


def ejecutar(con, archivo):
    with open(os.path.join(DIR, archivo), encoding="utf-8") as f:
        con.executescript(f.read())


def crear(ruta=DB, datos=True):
    if os.path.exists(ruta):
        os.remove(ruta)
    con = sqlite3.connect(ruta)
    ejecutar(con, "schema.sql")
    if datos:
        ejecutar(con, "datos_prueba.sql")
        _poner_claves(con)
    con.close()
    print(f"Base de datos creada: {ruta}")


def _poner_claves(con):
    for usuario, variable in CLAVES.items():
        clave = os.environ.get(variable)
        if not clave:
            clave = secrets.token_urlsafe(9)
            print(f"  {variable} no está en .env: la contraseña de {usuario} quedó en {clave}")
        con.execute("UPDATE usuario SET password_hash = ? WHERE username = ?",
                    (generate_password_hash(clave), usuario))
    con.commit()


def literal(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def exportar():
    con = sqlite3.connect(DB)
    # si la app uso modo WAL, se pasa todo al archivo .db antes de exportar
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    cur = con.cursor()
    tablas = dict(cur.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
    indices = [r[0] for r in cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY name")]
    disparadores = [r[0] for r in cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' ORDER BY name")]
    nombres = [t for t in ORDEN if t in tablas] + sorted(t for t in tablas if t not in ORDEN)

    lineas = [f"-- UBite - exportación de ubite.db ({datetime.now():%Y-%m-%d %H:%M:%S})",
              "BEGIN TRANSACTION;"]
    for t in nombres:
        lineas.append(tablas[t].replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1) + ";")
    for t in nombres:
        for fila in cur.execute(f'SELECT * FROM "{t}"'):
            lineas.append(f'INSERT INTO "{t}" VALUES (' + ",".join(literal(v) for v in fila) + ");")
    for sql in indices:
        lineas.append(sql.replace("INDEX ", "INDEX IF NOT EXISTS ", 1)
                      .replace("IF NOT EXISTS IF NOT EXISTS", "IF NOT EXISTS") + ";")
    for sql in disparadores:
        lineas.append(sql.replace("CREATE TRIGGER ", "CREATE TRIGGER IF NOT EXISTS ", 1)
                      .replace("IF NOT EXISTS IF NOT EXISTS", "IF NOT EXISTS") + ";")
    lineas.append("COMMIT;")
    con.close()

    with open(EXPORT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lineas) + "\n")
    print(f"Base de datos exportada: {EXPORT}")


if __name__ == "__main__":
    if "--exportar" not in sys.argv:
        crear()
    exportar()
