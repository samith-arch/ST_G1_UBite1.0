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
- Tecnologías definidas por el equipo: Python 3, Flask, SQLite. La guía de la asignatura toma
  SQL Server como referencia, pero permite otras tecnologías aprobadas; SQLite se aprobó en la
  Fase 1 porque no necesita instalar ni administrar un servidor, guarda toda la base en un
  archivo y soporta las transacciones ACID que necesita el prototipo local.
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
│   ├── etl.py               # comando flask etl: almacén de datos y datasets
│   ├── calendario.py        # festivos y periodos académicos de 2026
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
│   ├── ubite.db.sql         # exportación de la base con los datos de prueba
│   └── ubite.db             # se genera con crear_bd.py (no se sube al repositorio)
├── ia/                      # servicio de IA: red neuronal (TensorFlow) y API (FastAPI)
├── pruebas/                 # pruebas de las propiedades ACID (pytest)
├── docs/fase1/              # prototipo HTML de la Fase 1
├── .env.example             # variables de configuración, sin valores reales
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
- Implementado: aviso al celular con notificaciones web (Web Push) cuando el pedido está
  listo, con la página de seguimiento como respaldo.
- El pago en la aplicación queda simulado (pagos de prueba en los datos iniciales).
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
git clone https://github.com/samith-arch/ST_G1_UBite1.0.git
cd ST_G1_UBite1.0
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv
source venv/bin/activate   # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configurar el archivo `.env`

Las claves no se guardan en el código ni en el repositorio. Copiar `.env.example` como `.env`
(este archivo está en `.gitignore`) y llenar los valores:

```bash
copy .env.example .env      # en Linux o macOS: cp .env.example .env
```

| Variable | Para qué sirve |
|---|---|
| `UBITE_SECRET_KEY` | firma las sesiones; se puede generar con `python -c "import secrets; print(secrets.token_hex(32))"` |
| `UBITE_CLAVE_ADMIN` | contraseña del usuario `admin` que crea la base de prueba |
| `UBITE_CLAVE_CAJERO` | contraseña del usuario `acajero` que crea la base de prueba |
| `UBITE_CONTACTO` | correo que se envía con las notificaciones push |

La aplicación lee el `.env` con `python-dotenv`. Si falta `UBITE_SECRET_KEY` usa una clave
temporal y lo avisa en `logs/ubite.log`.

### 4. Crear la base de datos

La base `database/ubite.db` no se sube al repositorio, porque al probar la aplicación guarda
nombres y celulares de quien la usa. Se crea con:

```bash
python database/crear_bd.py
```

El script borra `ubite.db`, ejecuta `schema.sql` y `datos_prueba.sql` y deja la
exportación actualizada en `database/ubite.db.sql`. Las fechas de los registros son las
del momento en que se ejecuta.

También se puede hacer con **DB Browser for SQLite**: `New Database` → `database/ubite.db`,
pestaña **Execute SQL**, ejecutar `schema.sql` y luego `datos_prueba.sql`, `Write Changes`
y exportar con `File > Export > Database to SQL file` sobre `database/ubite.db.sql`.

Usuarios de prueba (solo entorno local): `acajero` (cajero) y `admin` (administrador). Sus
contraseñas son las que se pongan en el `.env`; en la base solo queda el hash. Si alguna
falta en el `.env`, el script genera una al azar y la muestra en la consola.

### 5. Pruebas de las propiedades ACID

```bash
python -m pytest pruebas -v
```

Las pruebas usan una base temporal aparte y revisan atomicidad (una falla a mitad del
registro no deja nada guardado), consistencia (la base rechaza stock negativo, estados
fuera de orden, subtotales mal calculados y pagos dobles), aislamiento (cinco personas
pidiendo la última unidad al mismo tiempo: solo una la obtiene) y durabilidad (lo
confirmado se lee desde otra conexión). Cada commit y rollback de la aplicación queda en
`logs/ubite.log`.

### 6. Ejecutar el proyecto

```bash
python run.py
```

La aplicación quedará disponible en:

- Cliente (la dirección a la que lleva el código QR): `http://127.0.0.1:5000/`
- Personal de la cafetería: `http://127.0.0.1:5000/personal/login`

Para probarla desde un celular conectado a la misma red Wi-Fi, ejecutar
`flask --app run run --host 0.0.0.0` y abrir `http://<IP-del-computador>:5000/`.

### 7. Notificaciones al celular

Los navegadores solo permiten notificaciones en páginas seguras (`https` o `localhost`).
Para probarlas desde un celular hay que abrir la aplicación por `https`, por ejemplo con
un túnel de Cloudflare:

```bash
cloudflared tunnel --url http://localhost:5000
```

El comando muestra una dirección `https://...trycloudflare.com` que se abre en el celular.
En iPhone, además, hay que agregar la página a la pantalla de inicio (Compartir → Agregar
a inicio) y abrirla desde ese ícono. Las claves de las notificaciones se crean solas la
primera vez en `instance/` y no se suben al repositorio.

---

### 8. Historial simulado, ETL y servicio de inteligencia artificial

UBite todavía no tiene meses de ventas reales, así que para entrenar la red neuronal se genera
un historial simulado de 2026 (unos 17.000 pedidos con código `S-#####`, clientes ficticios con
celular `3009…`). Se puede borrar en cualquier momento sin tocar los pedidos reales.

```bash
python database/historial_simulado.py          # genera el historial (o --borrar para quitarlo)
flask --app run etl --completo                  # llena database/ubite_dw.db y exporta ia/datos/*.csv
```

El ETL lee `ubite.db` en solo lectura, carga el almacén en estrella en una sola transacción y
exporta dos datasets sin datos personales: `dataset_ventas.csv` (una fila por producto vendido)
y `dataset_demanda.csv` (día × franja × producto, el que usa la red). El celular de cada
cliente se reemplaza por un código HMAC-SHA256 con la clave `UBITE_CLAVE_ANONIMA` del `.env`.

El servicio de IA vive en `ia/` y usa **Python 3.12** (TensorFlow no se instala en el entorno de
la aplicación), con su propio entorno virtual:

```bash
cd ia
py -3.12 -m venv .venv                          # en Linux: python3.12 -m venv .venv
.venv\Scripts\activate                          # en Linux: source .venv/bin/activate
pip install -r requirements.txt
python entrenar_modelo.py                       # entrena la red y la compara con el promedio
uvicorn api:app --port 8000                     # API en http://127.0.0.1:8000/docs
```

| Archivo | Qué hace |
|---|---|
| `ia/demanda.py` | Prepara las 62 entradas de la red (producto, día, franja, periodo académico y ventas de la semana anterior) |
| `ia/entrenar_modelo.py` | Entrena la red (Keras: 62 → 8 ReLU → 1), la prueba con las dos últimas semanas y guarda `modelo/modelo_demanda.keras` |
| `ia/api.py` | FastAPI: `POST /predecir` (unidades por franja de un producto) y `POST /alertas` (productos que se agotarían con el stock actual) |

Con la API encendida, el administrador ve en **Alertas de reposición** (`/admin/alertas`) qué productos se agotarían antes del cierre. Flask envía el stock real desde la media hora actual (o desde las 7:00 del siguiente día de apertura si ya cerró) y muestra cuántas unidades faltan. Si la API está apagada, la pantalla lo avisa y el resto de la aplicación sigue igual. La dirección se cambia con `UBITE_IA_URL` en el `.env`.

## Integrantes

- Pedraza Vanegas, Joseph
- Amariles Nieto, Samith

**Asignatura:** Sistemas Transaccionales
**Docente:** Jamilton Fernando Benavides
**Universidad Manuela Beltrán — Ingeniería de Software — Séptimo Semestre**
