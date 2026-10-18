import os
import sys
import tempfile

import pytest

# las pruebas usan una base aparte para no tocar database/ubite.db
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_PRUEBA = os.path.join(tempfile.gettempdir(), "ubite_pruebas.db")
os.environ["UBITE_DB"] = BASE_PRUEBA
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "database"))

import crear_bd  # noqa: E402
from app import create_app  # noqa: E402
from app.database import db  # noqa: E402

crear_bd.crear(BASE_PRUEBA)
_app = create_app()
_app.config["TESTING"] = True


@pytest.fixture
def app():
    # cada prueba arranca con la base recien creada
    with _app.app_context():
        db.session.remove()
        db.engine.dispose()
    crear_bd.crear(BASE_PRUEBA)
    with _app.app_context():
        yield _app
        db.session.remove()


@pytest.fixture
def cajero(app):
    from app.models import Usuario
    return Usuario.query.filter_by(username="acajero").first()
