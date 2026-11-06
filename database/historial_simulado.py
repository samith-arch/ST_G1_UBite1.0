# llena ubite.db con un historial de ventas simulado para entrenar la red neuronal
# y tener datos en el reporte, el historial y Power BI.
#
# los pedidos simulados usan el codigo S-00001, S-00002... asi no se mezclan con los
# A-### y P-### reales y se pueden borrar sin tocar lo demas.
#
#   python database/historial_simulado.py            genera desde febrero de 2026 hasta ayer
#   python database/historial_simulado.py --borrar   quita todo lo simulado
import math
import os
import random
import sqlite3
import sys
from datetime import date, datetime, timedelta

DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("UBITE_DB", os.path.join(DIR, "ubite.db"))

INICIO = date(2026, 2, 2)           # primera semana de clases del semestre 2026-1
SEMILLA = 2026

# festivos de Colombia en 2026 (ley Emiliani: los que se corren al lunes ya estan corridos)
FESTIVOS = {date(2026, 3, 23), date(2026, 4, 2), date(2026, 4, 3), date(2026, 5, 1), date(2026, 5, 18),
            date(2026, 6, 8), date(2026, 6, 15), date(2026, 6, 29), date(2026, 7, 20), date(2026, 8, 7),
            date(2026, 8, 17), date(2026, 10, 12), date(2026, 11, 2), date(2026, 11, 16)}

# calendario academico aproximado: (desde, hasta, multiplicador de la demanda)
PERIODOS = [
    (date(2026, 2, 2), date(2026, 2, 7), 0.8),        # primera semana de clases
    (date(2026, 3, 16), date(2026, 3, 21), 1.15),     # parciales 2026-1
    (date(2026, 3, 30), date(2026, 4, 4), 0.3),       # semana santa
    (date(2026, 5, 25), date(2026, 5, 30), 1.15),     # finales 2026-1
    (date(2026, 6, 15), date(2026, 8, 29), 0.25),     # intersemestral: solo cursos vacacionales
    (date(2026, 8, 31), date(2026, 9, 5), 0.8),       # primera semana 2026-2
    (date(2026, 9, 21), date(2026, 9, 26), 1.15),     # parciales 2026-2
]
EXAMENES = [p for p in PERIODOS if p[2] == 1.15]

# franjas de 30 minutos entre las 7:00 y las 19:00, con el peso de cada una:
# picos en los cambios de clase de la mañana, el almuerzo y la tarde
PESOS = {
    "07:00": 0.6, "07:30": 0.9, "08:00": 0.7, "08:30": 0.6, "09:00": 1.3, "09:30": 1.6,
    "10:00": 0.9, "10:30": 0.8, "11:00": 1.0, "11:30": 1.7, "12:00": 2.6, "12:30": 2.8,
    "13:00": 2.2, "13:30": 1.4, "14:00": 0.9, "14:30": 0.7, "15:00": 0.9, "15:30": 1.4,
    "16:00": 1.2, "16:30": 0.7, "17:00": 0.6, "17:30": 0.8, "18:00": 0.9, "18:30": 0.5,
}
# pedidos promedio en una franja de peso 1 segun el dia (lunes a sabado; domingo cerrado)
BASE_DIA = [4.0, 4.2, 4.0, 4.2, 3.4, 1.4, 0]

# que tanto se pide cada categoria segun la hora
PREFERENCIA = {
    "mañana": {"Bebidas": 1.4, "Snacks": 0.9, "Comidas": 0.8, "Panadería": 1.8},
    "almuerzo": {"Bebidas": 1.1, "Snacks": 0.5, "Comidas": 2.2, "Panadería": 0.4},
    "tarde": {"Bebidas": 1.2, "Snacks": 1.5, "Comidas": 0.6, "Panadería": 1.2},
}
# unos productos se venden mas que otros; lo caro sale menos
POPULARIDAD = {
    "Empanada": 1.8, "Agua en botella": 1.6, "Gaseosa": 1.3, "Gaseosa personal": 1.1, "Jugo en caja": 1.0,
    "Té frío": 0.9, "Bebida energizante": 0.6, "Malta": 0.6, "Bebida hidratante": 0.5, "Avena en vaso": 0.7,
    "Papas fritas": 1.2, "Platanitos": 0.9, "Galletas": 0.9, "Chocolatina": 0.8, "Maní salado": 0.6,
    "Chicharrón en paquete": 0.6, "Barra de cereal": 0.5, "Chupeta": 0.9,
    "Pastel de pollo": 1.1, "Papa rellena": 0.9, "Arepa de queso": 1.0, "Arepa rellena de pollo": 0.7,
    "Sándwich de jamón y queso": 0.6,
    "Pandebono": 1.3, "Almojábana": 0.9, "Buñuelo": 1.0, "Pastel de arequipe": 0.6,
}
# en semana de examenes se venden mas energizantes y te frio
EN_EXAMENES = {"Bebida energizante": 2.2, "Té frío": 1.3}
NOMBRES = ["Camila", "Andrés", "Mateo", "Laura", "Valentina", "Santiago", "Daniela", "Sebastián",
           "Sofía", "Nicolás", "Mariana", "Juan", "Isabella", "Felipe", "Gabriela", "David",
           "Paula", "Carlos", "Natalia", "Alejandro", "Juliana", "Miguel", "Sara", "Diego"]
APELLIDOS = ["Rojas", "Pérez", "Díaz", "Méndez", "Gómez", "Torres", "Ramírez", "Castro",
             "Moreno", "Vargas", "Herrera", "Suárez", "Ortiz", "Romero", "Cárdenas", "Ríos"]


def poisson(media):
    # numero de llegadas en una franja (algoritmo de Knuth, suficiente para medias pequeñas)
    limite, k, p = math.exp(-media), 0, 1.0
    while True:
        p *= random.random()
        if p <= limite:
            return k
        k += 1


def momento(franja):
    h = int(franja[:2])
    if h < 11:
        return "mañana"
    if h < 14:
        return "almuerzo"
    return "tarde"


def borrar(con):
    ids = "SELECT id_pedido FROM pedido WHERE codigo LIKE 'S-%'"
    for tabla in ("notificacion", "transaccion", "pago", "detalle_pedido"):
        con.execute(f"DELETE FROM {tabla} WHERE id_pedido IN ({ids})")
    n = con.execute("DELETE FROM pedido WHERE codigo LIKE 'S-%'").rowcount
    con.execute("DELETE FROM cliente WHERE telefono LIKE '3009%' "
                "AND id_cliente NOT IN (SELECT id_cliente FROM pedido)")
    return n


def generar(con):
    random.seed(SEMILLA)
    productos = con.execute(
        "SELECT p.id_producto, p.precio, c.nombre, p.nombre FROM producto p JOIN categoria c USING (id_categoria) "
        "WHERE p.activo = 1").fetchall()
    cajeros = [r[0] for r in con.execute("SELECT id_usuario FROM usuario WHERE rol = 'cajero'")]
    if not productos or not cajeros:
        sys.exit("La base no tiene productos o cajeros. Corre primero database/crear_bd.py")

    # clientes ficticios: los celulares empiezan por 3009 para reconocerlos al borrar
    clientes = []
    for i in range(600):
        nombre = f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)}"
        cur = con.execute("INSERT INTO cliente (nombre, telefono, fecha_registro) VALUES (?, ?, ?)",
                          (nombre, f"3009{i:06d}", f"{INICIO} 07:00:00"))
        clientes.append(cur.lastrowid)

    numero, dia, ayer = 0, INICIO, date.today() - timedelta(days=1)
    while dia <= ayer:
        base = 0 if dia in FESTIVOS else BASE_DIA[dia.weekday()]
        for desde, hasta, factor in PERIODOS:
            if desde <= dia <= hasta:
                base *= factor
        examenes = any(d <= dia <= h for d, h, _ in EXAMENES)
        for franja, peso in PESOS.items():
            for _ in range(poisson(base * peso * random.uniform(0.85, 1.15))):
                numero += 1
                _pedido(con, numero, dia, franja, productos, clientes, cajeros, examenes)
        dia += timedelta(days=1)
    return numero


def _pedido(con, numero, dia, franja, productos, clientes, cajeros, examenes):
    gusto = PREFERENCIA[momento(franja)]
    pesos = [gusto.get(cat, 1.0) * POPULARIDAD.get(nombre, 1.0) * (EN_EXAMENES.get(nombre, 1.0) if examenes else 1.0)
             for _, _, cat, nombre in productos]
    elegidos = {}
    for _ in range(random.choices([1, 2, 3], [0.55, 0.35, 0.10])[0]):
        id_producto, precio, _, _ = random.choices(productos, pesos)[0]
        elegidos[id_producto] = (elegidos.get(id_producto, (0, precio))[0] + random.choice([1, 1, 1, 2]), precio)

    h, m = int(franja[:2]), int(franja[3:]) + random.randint(0, 29)
    cuando = datetime(dia.year, dia.month, dia.day, h, m, random.randint(0, 59))
    qr = random.random() < 0.7
    cancelado = random.random() < 0.04
    cajero = random.choice(cajeros)
    total = sum(c * p for c, p in elegidos.values())

    cur = con.execute(
        "INSERT INTO pedido (codigo, id_cliente, id_usuario, fecha_hora, origen, estado, total) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (f"S-{numero:05d}", random.choice(clientes), None if qr else cajero, cuando.isoformat(" "),
         "qr" if qr else "presencial", "cancelado" if cancelado else "entregado", total))
    id_pedido = cur.lastrowid
    con.executemany(
        "INSERT INTO detalle_pedido (id_pedido, id_producto, cantidad, precio_unitario, subtotal) "
        "VALUES (?, ?, ?, ?, ?)",
        [(id_pedido, i, c, p, c * p) for i, (c, p) in elegidos.items()])
    con.execute("INSERT INTO transaccion (id_pedido, id_usuario, tipo, resultado, descripcion, fecha_hora) "
                "VALUES (?, ?, 'registro_pedido', 'confirmada', 'Historial simulado', ?)",
                (id_pedido, None if qr else cajero, cuando.isoformat(" ")))
    if cancelado:
        return
    # casi todos pagan en caja; algunos pedidos por QR se pagaron en la app (modo pruebas)
    en_app = qr and random.random() < 0.2
    con.execute("INSERT INTO pago (id_pedido, id_usuario, metodo, medio, estado, monto, referencia, fecha) "
                "VALUES (?, ?, ?, ?, 'aprobado', ?, ?, ?)",
                (id_pedido, None if en_app else cajero, "app" if en_app else "efectivo",
                 random.choice(["nequi", "daviplata"]) if en_app else None, total,
                 f"SIM-{numero:06d}" if en_app else None, cuando.isoformat(" ")))


if __name__ == "__main__":
    if not os.path.exists(DB):
        sys.exit(f"No existe {DB}. Corre primero: python database/crear_bd.py")
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    try:
        with con:
            quitados = borrar(con)
            if "--borrar" in sys.argv:
                print(f"Se quitaron {quitados} pedidos simulados.")
            else:
                n = generar(con)
                print(f"Historial simulado: {n} pedidos desde {INICIO} hasta ayer "
                      f"(se reemplazaron {quitados} anteriores).")
    finally:
        con.close()
