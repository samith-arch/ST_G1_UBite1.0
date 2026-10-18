"""Conexión a SQLite y manejo de transacciones.

Para que las propiedades ACID se cumplan en SQLite se hacen dos cosas:

1. Se desactiva el manejo automático de transacciones del módulo sqlite3 de
   Python (isolation_level = None) y es SQLAlchemy quien emite el BEGIN.
2. Las operaciones que escriben (registrar, modificar o cancelar un pedido,
   cambiar su estado, cobrarlo) se abren con BEGIN IMMEDIATE, que toma el
   permiso de escritura desde el inicio. Si dos clientes piden la última
   unidad de un producto al mismo tiempo, el segundo espera a que el primero
   termine y cuando continúa ya ve el stock actualizado.
"""
import os
from contextlib import contextmanager
from contextvars import ContextVar

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "database", "ubite.db")

db = SQLAlchemy()

# Indica si la transacción que se va a abrir es de escritura
_escritura = ContextVar("escritura", default=False)


def get_database_uri():
    return f"sqlite:///{DB_PATH}"


@event.listens_for(Engine, "connect")
def _configurar_sqlite(conexion, _registro):
    # SQLAlchemy se encarga del BEGIN, no el módulo sqlite3
    conexion.isolation_level = None
    cursor = conexion.cursor()
    # SQLite no revisa las llaves foráneas si no se activan en cada conexión
    cursor.execute("PRAGMA foreign_keys = ON")
    # Si otra transacción está escribiendo, se espera hasta 10 s antes de fallar
    cursor.execute("PRAGMA busy_timeout = 10000")
    cursor.close()


@event.listens_for(Engine, "begin")
def _iniciar_transaccion(conexion):
    conexion.exec_driver_sql("BEGIN IMMEDIATE" if _escritura.get() else "BEGIN")


@contextmanager
def transaccion():
    """Bloque de escritura atómico: todo lo que se haga dentro se confirma
    junto con COMMIT o se deshace completo con ROLLBACK si algo falla.

        with transaccion():
            ...  # leer y escribir con db.session
    """
    marca = _escritura.set(True)
    try:
        # Se cierra cualquier lectura abierta para que el nuevo BEGIN sea IMMEDIATE
        db.session.rollback()
        yield db.session
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    finally:
        _escritura.reset(marca)
