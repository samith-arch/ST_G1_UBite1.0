# pruebas de las propiedades ACID sobre el registro y la gestion de pedidos
import sqlite3
import threading

import pytest
from sqlalchemy.exc import IntegrityError

from app import servicios
from app.database import db
from app.models import Cliente, Pago, Pedido, Producto, Transaccion, Usuario
from app.servicios import ErrorNegocio
from conftest import BASE_PRUEBA


def contar(modelo):
    return db.session.query(modelo).count()


# atomicidad: o se guarda todo el pedido o no se guarda nada

def test_falla_a_mitad_no_deja_nada(app, monkeypatch):
    pedidos, clientes = contar(Pedido), contar(Cliente)
    stock = db.session.get(Producto, 4).stock_actual

    def falla(*a, **k):
        raise RuntimeError("se cayo el servidor a mitad del registro")
    monkeypatch.setattr(Transaccion, "registrar", falla)

    with pytest.raises(RuntimeError):
        servicios.registrar_pedido("Prueba", "3001112233", {4: 2})
    db.session.expire_all()
    assert contar(Pedido) == pedidos
    assert contar(Cliente) == clientes
    assert db.session.get(Producto, 4).stock_actual == stock


def test_un_producto_sin_stock_cancela_todo_el_pedido(app):
    agua = db.session.get(Producto, 1).stock_actual
    with pytest.raises(ErrorNegocio) as e:
        servicios.registrar_pedido("Prueba", "3001112233", {1: 2, 8: 999})
    assert e.value.faltantes
    db.session.expire_all()
    assert db.session.get(Producto, 1).stock_actual == agua


# consistencia: la base rechaza datos que rompen las reglas aunque el codigo falle

@pytest.mark.parametrize("sql", [
    "UPDATE producto SET stock_actual = -1 WHERE id_producto = 1",
    "UPDATE pedido SET estado = 'en_cola' WHERE codigo = 'P-001'",
    "INSERT INTO detalle_pedido (id_pedido, id_producto, cantidad, precio_unitario, subtotal) VALUES (2, 1, 2, 2500, 100)",
    "INSERT INTO pago (id_pedido, metodo, estado, monto) VALUES (1, 'efectivo', 'aprobado', 6000)",
    "INSERT INTO pedido (codigo, id_cliente, origen) VALUES ('A-001', 1, 'qr')",
])
def test_la_base_rechaza_datos_inconsistentes(app, sql):
    con = sqlite3.connect(BASE_PRUEBA)
    con.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.DatabaseError):
        con.execute(sql)
    con.close()


def test_total_igual_a_la_suma_de_detalles(app):
    codigo = servicios.registrar_pedido("Prueba", "3001112233", {1: 2, 7: 1})
    p = servicios.buscar_pedido(codigo)
    assert p.total == sum(d.subtotal for d in p.detalles) == 2 * 2500 + 3000


# aislamiento: pedidos al mismo tiempo no venden la misma unidad

def test_cinco_personas_piden_la_ultima_unidad(app):
    p = db.session.get(Producto, 6)
    p.stock_actual = 1
    db.session.commit()
    pedidos = contar(Pedido)
    db.session.remove()

    resultados, barrera = [], threading.Barrier(5)

    def pedir(i):
        with app.app_context():
            barrera.wait()
            try:
                servicios.registrar_pedido(f"Estudiante {i}", "3000000000", {6: 1})
                resultados.append("ok")
            except ErrorNegocio:
                resultados.append("sin stock")
            finally:
                db.session.remove()

    hilos = [threading.Thread(target=pedir, args=(i,)) for i in range(5)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]

    db.session.expire_all()
    assert resultados.count("ok") == 1
    assert resultados.count("sin stock") == 4
    assert db.session.get(Producto, 6).stock_actual == 0
    assert contar(Pedido) == pedidos + 1


def test_dos_cajeros_mueven_el_mismo_pedido(app, cajero):
    id_pedido = servicios.buscar_pedido("A-002").id_pedido
    id_cajero = cajero.id_usuario
    db.session.remove()
    resultados, barrera = [], threading.Barrier(2)

    def preparar():
        with app.app_context():
            barrera.wait()
            try:
                quien = db.session.get(Usuario, id_cajero)
                servicios.cambiar_estado(id_pedido, "en_preparacion", quien)
                resultados.append("ok")
            except ErrorNegocio:
                resultados.append("rechazado")
            finally:
                db.session.remove()

    hilos = [threading.Thread(target=preparar) for _ in range(2)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert sorted(resultados) == ["ok", "rechazado"]


# durabilidad: lo confirmado sigue ahi al abrir otra conexion

def test_lo_confirmado_queda_guardado(app):
    codigo = servicios.registrar_pedido("Prueba", "3001112233", {3: 1})
    db.session.remove()
    db.engine.dispose()

    con = sqlite3.connect(BASE_PRUEBA)
    fila = con.execute("SELECT estado, total FROM pedido WHERE codigo = ?", (codigo,)).fetchone()
    tx = con.execute("SELECT tipo, resultado FROM transaccion t JOIN pedido p USING(id_pedido) "
                     "WHERE p.codigo = ?", (codigo,)).fetchall()
    con.close()
    assert fila == ("en_cola", 2500)
    assert ("registro_pedido", "confirmada") in tx


# errores de la operacion

def test_no_se_cobra_dos_veces_un_pedido_pagado(app, cajero):
    pedido = servicios.buscar_pedido("A-001")  # ya pagado en la app y listo
    with pytest.raises(ErrorNegocio) as e:
        servicios.entregar_o_rechazar(pedido.id_pedido, cajero, cobrar=True)
    assert e.value.titulo == "Este pedido ya está pagado"
    db.session.expire_all()
    assert Pago.query.filter_by(id_pedido=pedido.id_pedido, estado="aprobado").count() == 1
    ultima = Transaccion.query.order_by(Transaccion.id_transaccion.desc()).first()
    assert ultima.resultado == "revertida"


def test_el_doble_toque_no_duplica_el_pedido(app):
    c = app.test_client()
    with c.session_transaction() as s:
        s["_csrf"] = "t"
        s["cliente"] = {"nombre": "Prueba", "telefono": "3001112233"}
        s["carrito"] = {"5": 1}
    antes = contar(Pedido)
    datos = {"_csrf": "t", "envio": "mismo-envio"}
    r1 = c.post("/pedido/confirmar", data=datos)
    with c.session_transaction() as s:
        s["carrito"] = {"5": 1}
    r2 = c.post("/pedido/confirmar", data=datos)
    assert r1.location == r2.location
    assert contar(Pedido) == antes + 1
