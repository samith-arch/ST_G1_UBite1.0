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


MARCA = "Historial simulado"
VOLUMEN = 1.75              # mas pedidos por franja que la primera version (unos 30.000 en total)
FALLA_PROVEEDOR = 0.025     # probabilidad de que un producto no llegue en la mañana
SUSTITUYE, QUITA = 0.55, 0.30   # lo que hace el cliente si le falta algo; el resto se va sin comprar


def _tablas_nuevas(con):
    # bases creadas antes de que existieran estas dos tablas
    import re
    with open(os.path.join(DIR, "schema.sql"), encoding="utf-8") as f:
        esquema = f.read()
    for tabla in ("agotamiento", "operacion_rechazada"):
        con.execute(re.search(rf'CREATE TABLE IF NOT EXISTS "{tabla}" \(.*?\n\);', esquema, re.S).group(0))


def borrar(con):
    ids = "SELECT id_pedido FROM pedido WHERE codigo LIKE 'S-%'"
    for tabla in ("notificacion", "transaccion", "pago", "detalle_pedido"):
        con.execute(f"DELETE FROM {tabla} WHERE id_pedido IN ({ids})")
    con.execute(f"DELETE FROM operacion_rechazada WHERE detalle LIKE '%{MARCA.lower()}'")
    con.execute(f"DELETE FROM agotamiento WHERE nota LIKE '{MARCA}%'")
    n = con.execute("DELETE FROM pedido WHERE codigo LIKE 'S-%'").rowcount
    con.execute("DELETE FROM cliente WHERE telefono LIKE '3009%' "
                "AND id_cliente NOT IN (SELECT id_cliente FROM pedido)")
    return n


class Bodega:
    # stock simulado de cada producto: se repone cada mañana segun lo que se ha venido pidiendo
    def __init__(self, con, productos):
        self.con, self.productos = con, {p[0]: p for p in productos}
        self.stock = {p[0]: 12 for p in productos}
        self.promedio = {p[0]: 10.0 for p in productos}
        self.pedido_hoy = {p[0]: 0 for p in productos}
        self.agotado = {}       # id_producto -> id_agotamiento abierto
        self.sin_entrega = set()
        self.fallas = 0

    def abrir_dia(self, dia):
        manana = datetime(dia.year, dia.month, dia.day, 6, 50)
        self.sin_entrega = set()
        for i in self.productos:
            if random.random() < FALLA_PROVEEDOR:
                self.fallas += 1
                self.sin_entrega.add(i)
                if i in self.agotado:
                    self._sin_reposicion(self.agotado[i])
                continue
            nivel = math.ceil(self.promedio[i] * random.uniform(1.15, 1.6)) + 3
            if self.stock[i] < nivel:
                self.stock[i] = nivel
                self._cerrar(i, manana)

    def cerrar_dia(self):
        for i in self.productos:
            self.promedio[i] = 0.8 * self.promedio[i] + 0.2 * self.pedido_hoy[i]
            self.pedido_hoy[i] = 0

    def descontar(self, i, cantidad, cuando):
        self.stock[i] -= cantidad
        if self.stock[i] == 0 and i not in self.agotado:
            cur = self.con.execute("INSERT INTO agotamiento (id_producto, desde, nota) VALUES (?, ?, ?)",
                                   (i, cuando.isoformat(" "), MARCA))
            self.agotado[i] = cur.lastrowid
            if i in self.sin_entrega:
                self._sin_reposicion(cur.lastrowid)

    def _sin_reposicion(self, id_agotamiento):
        self.con.execute("UPDATE agotamiento SET sin_reposicion = 1, nota = ? WHERE id_agotamiento = ?",
                         (f"{MARCA}: el proveedor no llegó", id_agotamiento))

    def _cerrar(self, i, cuando):
        if i in self.agotado:
            self.con.execute("UPDATE agotamiento SET hasta = ? WHERE id_agotamiento = ?",
                             (cuando.isoformat(" "), self.agotado.pop(i)))

    def cerrar_todo(self, dia):
        # lo que siga agotado al final se cierra para no confundir el inventario real
        fin = datetime(dia.year, dia.month, dia.day, 19, 0)
        for i in list(self.agotado):
            self._cerrar(i, fin)


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
    for i in range(900):
        nombre = f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)}"
        cur = con.execute("INSERT INTO cliente (nombre, telefono, fecha_registro) VALUES (?, ?, ?)",
                          (nombre, f"3009{i:06d}", f"{INICIO} 07:00:00"))
        clientes.append(cur.lastrowid)

    bodega = Bodega(con, productos)
    cuenta = {"pedidos": 0, "rechazos": 0, "perdidos": 0, "querido": {}}
    dia, ayer = INICIO, date.today() - timedelta(days=1)
    while dia <= ayer:
        base = 0 if dia in FESTIVOS else BASE_DIA[dia.weekday()] * VOLUMEN
        for desde, hasta, factor in PERIODOS:
            if desde <= dia <= hasta:
                base *= factor
        if base:
            bodega.abrir_dia(dia)
        examenes = any(d <= dia <= h for d, h, _ in EXAMENES)
        for franja, peso in PESOS.items():
            for _ in range(poisson(base * peso * random.uniform(0.85, 1.15))):
                _cliente(con, cuenta, bodega, dia, franja, productos, clientes, cajeros, examenes)
        if base:
            bodega.cerrar_dia()
        dia += timedelta(days=1)
    bodega.cerrar_todo(ayer)
    cuenta["fallas"] = bodega.fallas
    _guardar_querido(cuenta.pop("querido"))
    cuenta["agotamientos"] = con.execute("SELECT COUNT(*) FROM agotamiento WHERE nota LIKE ?", (MARCA + "%",)).fetchone()[0]
    return cuenta


def _guardar_querido(querido):
    # solo en lo simulado se sabe cuanto se queria comprar de verdad, aunque no hubiera;
    # entrenar_modelo.py lo usa para medir si la red aprende bien la demanda
    import csv
    carpeta = os.path.join(os.path.dirname(DIR), "ia", "datos")
    os.makedirs(carpeta, exist_ok=True)
    with open(os.path.join(carpeta, "demanda_simulada.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fecha", "id_franja", "id_producto", "unidades_queridas"])
        w.writerows(sorted(k + (v,) for k, v in querido.items()))


def _cliente(con, cuenta, bodega, dia, franja, productos, clientes, cajeros, examenes):
    gusto = PREFERENCIA[momento(franja)]
    pesos = [gusto.get(cat, 1.0) * POPULARIDAD.get(nombre, 1.0) * (EN_EXAMENES.get(nombre, 1.0) if examenes else 1.0)
             for _, _, cat, nombre in productos]
    elegidos = {}
    for _ in range(random.choices([1, 2, 3], [0.55, 0.35, 0.10])[0]):
        id_producto, precio, _, _ = random.choices(productos, pesos)[0]
        elegidos[id_producto] = (elegidos.get(id_producto, (0, precio))[0] + random.choice([1, 1, 1, 2]), precio)
    clave_franja = (dia.isoformat(), int(franja[:2]) * 2 + (1 if franja[3:] == "30" else 0))
    for i, (c, _) in elegidos.items():
        bodega.pedido_hoy[i] += c
        cuenta["querido"][clave_franja + (i,)] = cuenta["querido"].get(clave_franja + (i,), 0) + c

    h, m = int(franja[:2]), int(franja[3:]) + random.randint(0, 29)
    cuando = datetime(dia.year, dia.month, dia.day, h, m, random.randint(0, 59))
    qr = random.random() < 0.7
    cajero = random.choice(cajeros)

    faltan = {i: c for i, (c, _) in elegidos.items() if bodega.stock[i] < c}
    if faltan:
        # igual que en la app: el pedido completo se rechaza y queda en el historial
        detalle = "; ".join(f"{bodega.productos[i][3]}: pediste {c} · quedan {bodega.stock[i]}" for i, c in faltan.items())
        con.execute("INSERT INTO operacion_rechazada (id_usuario, operacion, origen, fecha_hora, motivo, detalle) "
                    "VALUES (?, 'registro_pedido', ?, ?, 'Sin stock suficiente', ?)",
                    (None if qr else cajero, "qr" if qr else "presencial", cuando.isoformat(" "),
                     f"{detalle} · {MARCA.lower()}"))
        cuenta["rechazos"] += 1
        cuando += timedelta(seconds=random.randint(20, 90))
        reaccion = random.random()
        for i, c in faltan.items():
            del elegidos[i]
            if reaccion < SUSTITUYE:
                cat = bodega.productos[i][2]
                opciones = [p for p in productos if p[2] == cat and p[0] != i and bodega.stock[p[0]] >= c
                            and p[0] not in elegidos]
                if opciones:
                    otro = random.choice(opciones)
                    elegidos[otro[0]] = (c, otro[1])
        if not elegidos or reaccion >= SUSTITUYE + QUITA:
            cuenta["perdidos"] += 1
            return

    cuenta["pedidos"] += 1
    numero = cuenta["pedidos"]
    cancelado = random.random() < 0.04
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
                "VALUES (?, ?, 'registro_pedido', 'confirmada', ?, ?)",
                (id_pedido, None if qr else cajero, MARCA, cuando.isoformat(" ")))
    if cancelado:
        # al cancelar el stock vuelve, asi que en la bodega no se descuenta
        return
    for i, (c, _) in elegidos.items():
        bodega.descontar(i, c, cuando)
    con.execute("INSERT INTO pago (id_pedido, id_usuario, metodo, medio, estado, monto, referencia, fecha) "
                "VALUES (?, ?, 'efectivo', NULL, 'aprobado', ?, NULL, ?)",
                (id_pedido, cajero, total, cuando.isoformat(" ")))


if __name__ == "__main__":
    if not os.path.exists(DB):
        sys.exit(f"No existe {DB}. Corre primero: python database/crear_bd.py")
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    try:
        with con:
            _tablas_nuevas(con)
            quitados = borrar(con)
            if "--borrar" in sys.argv:
                print(f"Se quitaron {quitados} pedidos simulados.")
            else:
                r = generar(con)
                print(f"Historial simulado desde {INICIO} hasta ayer: {r['pedidos']} pedidos, "
                      f"{r['rechazos']} intentos rechazados por falta de stock "
                      f"({r['perdidos']} clientes se fueron sin comprar), {r['agotamientos']} agotamientos "
                      f"y {r['fallas']} veces que un proveedor no llegó. Se reemplazaron {quitados} pedidos anteriores.")
    finally:
        con.close()
