# ST_G1_UBite1.0

## UBite — Sistema transaccional para la gestión de pedidos en una cafetería universitaria

Se busca implementar un sistema transaccional que permita a los estudiantes y personal
universitario realizar sus pedidos mediante un código QR, evitando en cierta medida las
filas en la cafetería. El sistema debe redirigir a una página web donde se haga el pedido
a través de un formulario que solicite datos de contacto y posteriormente enviar una
notificación al teléfono del usuario cuando el pedido ya esté listo.

---

## 1. Introducción y objetivos

### 1.1 Requerimientos funcionales

- Escanear un código QR ubicado en la cafetería
- Diligenciar un formulario con datos como: nombre, teléfono y el pedido
- Enviar el pedido al sistema para procesarlo
- Recibir una notificación en el teléfono cuando el pedido esté listo
- Consultar el historial de pedidos
- Generar un reporte diario de ventas

### 1.2 Objetivo central

Diseñar un sistema transaccional que permita a los estudiantes y al personal de una
cafetería universitaria realizar pedidos mediante un código QR, garantizando el registro
consistente y seguro durante cada transacción, el control automático del stock de los
productos y la reducción de los tiempos de espera en el punto físico.

### 1.3 Stakeholders

| Rol | Interés |
|---|---|
| Cliente (estudiante/personal) | Hacer pedidos sin filas y recibir notificación cuando estén listos |
| Cajero | Registrar y gestionar pedidos entrantes |
| Administrador | Controlar inventario, ventas y usuarios del sistema |
| Docente (Jamilton Fernando Benavides) | Evaluador del proyecto de la asignatura |

## 2. Restricciones

- Proyecto académico desarrollado como prototipo local, sin despliegue en servidor
  institucional ni integración con pasarelas de pago reales.
- Tecnologías definidas por el equipo: Python 3, Flask, SQLite.
- Entrega por fases, manteniendo correspondencia con lo definido en fases anteriores
  (prototipo en Fase 1, modelo relacional en Fase 2).

## 3. Alcance y contexto del sistema

El sistema conecta tres tipos de actores: el cliente (vía navegador, al escanear el QR),
el cajero/administrador (vía interfaz interna) y la base de datos que centraliza clientes,
productos, pedidos, pagos, transacciones y notificaciones.

## 4. Estrategia de solución

Arquitectura en capas lógicas (Interfaz Web, Lógica de Negocio, Gestión de Transacciones
con propiedades ACID, Acceso a Datos, Base de Datos), con un componente transversal de
Seguridad que valida cada operación según el rol del usuario (cliente, cajero,
administrador).

## 5. Vista de bloques de construcción
```text
ubite/
├── app/
│   ├── __init__.py          # crea la aplicación Flask, sesión, CSRF y blueprints
│   ├── database.py          # conexión a SQLite y transacciones (BEGIN IMMEDIATE, commit/rollback)
│   ├── models.py            # modelos SQLAlchemy (1:1 con el modelo relacional)
│   ├── servicios.py         # lógica de negocio y coordinación de transacciones
│   ├── gestion.py           # reporte, inventario, clientes y usuarios
│   ├── routes/
│   │   ├── __init__.py      # control de acceso por rol
│   │   ├── cliente.py       # QR, menú, carrito, pedido, seguimiento, modificar y cancelar
│   │   ├── auth.py          # inicio de sesión del personal (Flask-Login)
│   │   ├── caja.py          # cola de pedidos, cobro en caja, pedido presencial, historial
│   │   ├── inventario.py    # inventario, entradas de stock y productos
│   │   └── admin.py         # reporte del día, clientes, usuarios y código QR
│   ├── templates/           # vistas HTML (Jinja2 + Bootstrap)
│   └── static/              # CSS, JavaScript, Bootstrap, íconos y fuentes locales
├── database/
│   ├── schema.sql           # creación de las 9 tablas (PK, FK, CHECK, UNIQUE, índices)
│   ├── datos_prueba.sql     # datos iniciales de prueba
│   ├── crear_bd.py          # crea ubite.db y la exporta a ubite.db.sql
│   ├── ubite.db.sql         # exportación de la base (DB Browser for SQLite)
│   └── ubite.db             # archivo de base de datos
├── requirements.txt
├── run.py                   # punto de entrada de la aplicación
└── README.md
```


## 6. Vista de tiempo de ejecución

Flujo de una transacción: el cliente interactúa con la interfaz web → la solicitud pasa
a la lógica de negocio, que valida disponibilidad de productos y calcula el total → se
delega el registro al módulo de gestión de transacciones (ACID) → este usa la capa de
acceso a datos para leer/escribir en la base de datos → la respuesta (confirmación, error
o notificación) recorre el mismo camino de vuelta al usuario. El componente de Seguridad
verifica cada interacción a lo largo de todo el flujo.

## 7. Vista de despliegue

Prototipo local: la base de datos SQLite corre como archivo local (`database/ubite.db`)
y el backend Flask se ejecuta en modo desarrollo. No hay despliegue en servidor de
producción en esta fase.

## 8. Conceptos transversales

- **Propiedades ACID** aplicadas al registro de pedidos, evitando duplicados o registros
  incompletos.
- **Seguridad basada en roles** (cliente, cajero, administrador) validada en cada
  operación del sistema.
- **Descuento automático de inventario** al confirmarse un pedido, sobre el stock de cada
  producto (`producto.stock_actual`); el stock se devuelve si el pedido se cancela.
- **Trazabilidad**: cada operación queda en la tabla `transaccion` (confirmada o revertida).

## 9. Decisiones de arquitectura

| Decisión | Justificación |
|---|---|
| Arquitectura en capas (no microservicios) | Más sencilla de implementar con las tecnologías propuestas para el alcance del proyecto |
| SQLite como motor de base de datos | Suficiente para un prototipo local, sin necesidad de un servidor de base de datos dedicado |
| SQLAlchemy como ORM | Desacopla la lógica de negocio del acceso a datos, facilitando el cumplimiento de ACID |

## 10. Requisitos de calidad

- Consistencia: cada pedido debe reflejar correctamente el inventario disponible.
- Disponibilidad de información: el cliente debe poder consultar disponibilidad antes de
  confirmar el pedido.
- Trazabilidad: debe existir historial de pedidos y reporte diario de ventas.

## 11. Riesgos y deuda técnica

- Implementado: flujo del cliente (QR, menú con stock, pedido, seguimiento, aviso de
  pedido listo, modificar y cancelar en cola) y panel del cajero (cola con prioridad,
  preparación, listo, cobro y entrega, cancelación en caja, pedido presencial cobrado al
  registrarlo e historial del día). Los pedidos por QR usan el código A-001 y los
  presenciales P-001.
- Implementado para el personal: inventario con alertas de stock mínimo y entradas de
  stock (cajero y administrador); para el administrador, creación y edición de productos,
  reporte del día con exportación a CSV, clientes, usuarios (crear, activar o desactivar,
  cambiar contraseña, ver quién está en línea) y código QR para imprimir.
- Pendiente: pago en la aplicación con pasarela en modo de pruebas y notificaciones Web Push.
- El aviso al celular se hará con notificaciones web (Web Push); depende de que el cliente
  dé permiso en el navegador, por eso se mantiene la página de seguimiento como respaldo.

## 12. Glosario

| Término | Definición |
|---|---|
| ACID | Atomicidad, Consistencia, Aislamiento, Durabilidad — propiedades que garantizan transacciones confiables |
| Pedido | Solicitud de uno o más productos realizada por un cliente |

---

## Instrucciones de ejecución

### Requisitos previos

- Python 3.10 o superior
- [DB Browser for SQLite](https://sqlitebrowser.org/)

### 1. Clonar el repositorio

```bash
git clone https://github.com/<usuario>/ST_G1_UBite1.0.git
cd ST_G1_UBite1.0
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv
source venv/bin/activate   # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Crear la base de datos

El repositorio ya incluye `database/ubite.db`. Para volver a crearla desde cero:

```bash
python database/crear_bd.py
```

El script borra `ubite.db`, ejecuta `schema.sql` y `datos_prueba.sql` y deja la
exportación actualizada en `database/ubite.db.sql`. Las fechas de los registros son las
del momento en que se ejecuta.

También se puede hacer con **DB Browser for SQLite**: `New Database` → `database/ubite.db`,
pestaña **Execute SQL**, ejecutar `schema.sql` y luego `datos_prueba.sql`, `Write Changes`
y exportar con `File > Export > Database to SQL file` sobre `database/ubite.db.sql`.

Usuarios de prueba (solo entorno local):

| Rol | Usuario | Contraseña |
|---|---|---|
| Cajero | `acajero` | `Cajero2026*` |
| Administrador | `admin` | `Admin2026*` |

### 4. Ejecutar el proyecto

```bash
python run.py
```

La aplicación quedará disponible en:

- Cliente (la dirección a la que lleva el código QR): `http://127.0.0.1:5000/`
- Personal de la cafetería: `http://127.0.0.1:5000/personal/login`

Para probarla desde un celular conectado a la misma red Wi-Fi, ejecutar
`flask --app run run --host 0.0.0.0` y abrir `http://<IP-del-computador>:5000/`.

---

## Integrantes

- Pedraza Vanegas, Joseph
- Amariles Nieto, Samith

**Asignatura:** Sistemas Transaccionales
**Docente:** Jamilton Fernando Benavides
**Universidad Manuela Beltrán — Ingeniería de Software — Séptimo Semestre**
