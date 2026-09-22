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
- Diligenciar un formulario con datos como: nombre, teléfono o correo y el pedido
- Enviar el pedido al sistema para procesarlo
- Recibir una notificación en el teléfono cuando el pedido esté listo
- Consultar el historial de pedidos
- Generar un reporte diario de ventas

### 1.2 Objetivo central

Diseñar un sistema transaccional que permita a los estudiantes y al personal de una
cafetería universitaria realizar pedidos mediante un código QR, garantizando el registro
consistente y seguro durante cada transacción, el control automático del inventario de
insumos y la reducción de los tiempos de espera en el punto físico.

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
productos, insumos y pedidos.

## 4. Estrategia de solución

Arquitectura en capas lógicas (Interfaz Web, Lógica de Negocio, Gestión de Transacciones
con propiedades ACID, Acceso a Datos, Base de Datos), con un componente transversal de
Seguridad que valida cada operación según el rol del usuario (cliente, cajero,
administrador).

## 5. Vista de bloques de construcción
ubite/
├── app/
│ ├── init.py # factory de la aplicación Flask
│ ├── models.py # modelos SQLAlchemy (refleja el modelo relacional)
│ ├── database.py # configuración de conexión a SQLite
│ └── routes/ # rutas del sistema (se implementan en fases siguientes)
├── database/
│ ├── ubite.sql # script exportado desde DB Browser for SQLite
│ └── ubite.db # archivo de base de datos
├── requirements.txt
├── run.py # punto de entrada de la aplicación
└── README.md


## 6. Vista de tiempo de ejecución

Flujo de una transacción: el cliente interactúa con la interfaz web → la solicitud pasa
a la lógica de negocio, que valida disponibilidad de insumos y calcula el total → se
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
- **Descuento automático de inventario** al confirmarse una venta, mediante la relación
  producto-insumo.

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

- Aún no se implementan las operaciones CRUD completas ni la interfaz de usuario (se
  desarrollan en fases posteriores).
- El envío de notificaciones al teléfono del usuario está definido a nivel de
  requerimiento, pero su mecanismo concreto (SMS, push, correo) está pendiente de
  decisión técnica.

## 12. Glosario

| Término | Definición |
|---|---|
| ACID | Atomicidad, Consistencia, Aislamiento, Durabilidad — propiedades que garantizan transacciones confiables |
| Insumo | Materia prima usada para preparar un producto (ej. café, leche, pan) |
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

1. Abrir **DB Browser for SQLite**.
2. `New Database` → guardar como `database/ubite.db` dentro del repositorio clonado.
3. Ir a la pestaña **Execute SQL**, pegar el contenido de `database/ubite.sql` y ejecutar
   (▶ Execute).
4. `Write Changes` para guardar los cambios en el archivo `.db`.

### 4. Ejecutar el proyecto

```bash
python run.py
```

La aplicación quedará disponible en `http://127.0.0.1:5000`.

---

## Integrantes

- Tovar Valencia, Juan David
- Pedraza Vanegas, Joseph
- Amariles Nieto, Samith

**Asignatura:** Sistemas Transaccionales
**Docente:** Jamilton Fernando Benavides
**Universidad Manuela Beltrán — Ingeniería de Software — Séptimo Semestre**
