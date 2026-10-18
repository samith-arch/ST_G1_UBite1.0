import os
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "database", "ubite.db")

db = SQLAlchemy()
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
    cursor.execute("PRAGMA busy_timeout = 10000")
    cursor.close()


@event.listens_for(Engine, "begin")
def _iniciar(conexion):
    # las escrituras toman el bloqueo desde el inicio (BEGIN IMMEDIATE),
    # asi dos pedidos al tiempo no pueden vender la misma unidad
    conexion.exec_driver_sql("BEGIN IMMEDIATE" if _escritura.get() else "BEGIN")


@contextmanager
def transaccion():
    marca = _escritura.set(True)
    try:
        db.session.rollback()
        yield db.session
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    finally:
        _escritura.reset(marca)
