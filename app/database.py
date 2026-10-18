import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# UBITE_DB permite usar otra base, por ejemplo en las pruebas
DB_PATH = os.environ.get("UBITE_DB", os.path.join(BASE_DIR, "database", "ubite.db"))

db = SQLAlchemy()
log = logging.getLogger("ubite.transacciones")
_escritura = ContextVar("escritura", default=False)


def get_database_uri():
    return f"sqlite:///{DB_PATH}"


def revisar_base():
    # si el archivo no existe sqlite crea uno vacio, mejor avisar de una vez
    tablas = 0
    if os.path.exists(DB_PATH):
        con = sqlite3.connect(DB_PATH)
        tablas = con.execute("SELECT count(*) FROM sqlite_master WHERE name = 'pedido'").fetchone()[0]
        con.close()
    if not tablas:
        raise SystemExit("La base de datos no existe o está vacía. "
                         "Ejecuta primero: python database/crear_bd.py")


@event.listens_for(Engine, "connect")
def _configurar_sqlite(conexion, _registro):
    # el BEGIN lo manda sqlalchemy y no el modulo sqlite3
    conexion.isolation_level = None
    cursor = conexion.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA busy_timeout = 5000")
    # WAL: las lecturas (paginas, reportes) no frenan a quien esta escribiendo;
    # sigue habiendo un solo escritor a la vez
    cursor.execute("PRAGMA journal_mode = WAL")
    # FULL: el commit no se da por hecho hasta que esta escrito en disco
    cursor.execute("PRAGMA synchronous = FULL")
    cursor.close()


@event.listens_for(Engine, "begin")
def _iniciar(conexion):
    # las escrituras toman el bloqueo desde el inicio (BEGIN IMMEDIATE),
    # asi dos pedidos al tiempo no pueden vender la misma unidad
    conexion.exec_driver_sql("BEGIN IMMEDIATE" if _escritura.get() else "BEGIN")


@contextmanager
def transaccion(nombre="operacion"):
    marca = _escritura.set(True)
    inicio = time.perf_counter()
    try:
        db.session.rollback()
        yield db.session
        db.session.commit()
        log.info("COMMIT   %-22s %.0f ms", nombre, (time.perf_counter() - inicio) * 1000)
    except Exception as e:
        db.session.rollback()
        log.warning("ROLLBACK %-22s %s: %s", nombre, type(e).__name__, str(e).splitlines()[0][:120])
        raise
    finally:
        _escritura.reset(marca)


class BaseOcupada(Exception):
    pass


def reintentar(funcion):
    # si otra transaccion tiene la base ocupada mas de 5 s se intenta otra vez,
    # hasta tres veces, antes de mostrar el error
    @wraps(funcion)
    def envoltura(*args, **kwargs):
        for intento in range(3):
            try:
                return funcion(*args, **kwargs)
            except OperationalError as e:
                if "locked" not in str(e) and "busy" not in str(e):
                    raise
                log.warning("base ocupada en %s, intento %d", funcion.__name__, intento + 1)
                time.sleep(0.3 * (intento + 1))
        raise BaseOcupada()
    return envoltura
