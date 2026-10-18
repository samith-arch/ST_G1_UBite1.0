-- =====================================================================
-- UBite - Esquema de la base de datos (SQLite)
-- Sigue el modelo relacional corregido de la Fase 2:
-- 9 tablas, inventario como stock en producto (sin insumo ni
-- producto_insumo), pedido en cola, pago en app o en caja,
-- trazabilidad en transaccion y avisos en notificacion.
-- Las fechas se guardan con la hora local del equipo donde se ejecuta.
-- =====================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

DROP TABLE IF EXISTS "producto_insumo";
DROP TABLE IF EXISTS "insumo";
DROP TABLE IF EXISTS "notificacion";
DROP TABLE IF EXISTS "transaccion";
DROP TABLE IF EXISTS "pago";
DROP TABLE IF EXISTS "detalle_pedido";
DROP TABLE IF EXISTS "pedido";
DROP TABLE IF EXISTS "producto";
DROP TABLE IF EXISTS "categoria";
DROP TABLE IF EXISTS "usuario";
DROP TABLE IF EXISTS "cliente";

-- Cliente: solo nombre y celular (Ley 1581 de 2012).
-- suscripcion_push guarda la suscripción del navegador para el aviso al celular.
CREATE TABLE IF NOT EXISTS "cliente" (
	"id_cliente"	INTEGER,
	"nombre"	TEXT NOT NULL,
	"telefono"	TEXT NOT NULL,
	"fecha_registro"	DATETIME NOT NULL DEFAULT (datetime('now','localtime')),
	"suscripcion_push"	TEXT,
	PRIMARY KEY("id_cliente" AUTOINCREMENT)
);

-- Usuario: personal de la cafetería (cajero o administrador).
CREATE TABLE IF NOT EXISTS "usuario" (
	"id_usuario"	INTEGER,
	"nombre"	TEXT NOT NULL,
	"rol"	TEXT NOT NULL CHECK("rol" IN ('cajero', 'administrador')),
	"username"	TEXT NOT NULL UNIQUE,
	"password_hash"	TEXT NOT NULL,
	"activo"	BOOLEAN NOT NULL DEFAULT 1 CHECK("activo" IN (0, 1)),
	PRIMARY KEY("id_usuario" AUTOINCREMENT)
);

CREATE TABLE IF NOT EXISTS "categoria" (
	"id_categoria"	INTEGER,
	"nombre"	TEXT NOT NULL UNIQUE,
	PRIMARY KEY("id_categoria" AUTOINCREMENT)
);

-- Producto: el inventario se maneja como stock por producto.
CREATE TABLE IF NOT EXISTS "producto" (
	"id_producto"	INTEGER,
	"nombre"	TEXT NOT NULL,
	"descripcion"	TEXT,
	"precio"	REAL NOT NULL CHECK("precio" > 0),
	"stock_actual"	INTEGER NOT NULL DEFAULT 0 CHECK("stock_actual" >= 0),
	"stock_minimo"	INTEGER NOT NULL DEFAULT 0 CHECK("stock_minimo" >= 0),
	"activo"	BOOLEAN NOT NULL DEFAULT 1 CHECK("activo" IN (0, 1)),
	"id_categoria"	INTEGER NOT NULL,
	PRIMARY KEY("id_producto" AUTOINCREMENT),
	FOREIGN KEY("id_categoria") REFERENCES "categoria"("id_categoria")
);

-- Pedido: entra en cola apenas se confirma.
-- id_usuario es NULL en pedidos por QR y es el cajero en pedidos presenciales.
CREATE TABLE IF NOT EXISTS "pedido" (
	"id_pedido"	INTEGER,
	"codigo"	TEXT NOT NULL UNIQUE,
	"id_cliente"	INTEGER NOT NULL,
	"id_usuario"	INTEGER,
	"fecha_hora"	DATETIME NOT NULL DEFAULT (datetime('now','localtime')),
	"origen"	TEXT NOT NULL CHECK("origen" IN ('qr', 'presencial')),
	"estado"	TEXT NOT NULL DEFAULT 'en_cola' CHECK("estado" IN ('en_cola', 'en_preparacion', 'listo', 'entregado', 'cancelado')),
	"total"	REAL NOT NULL DEFAULT 0 CHECK("total" >= 0),
	PRIMARY KEY("id_pedido" AUTOINCREMENT),
	FOREIGN KEY("id_cliente") REFERENCES "cliente"("id_cliente"),
	FOREIGN KEY("id_usuario") REFERENCES "usuario"("id_usuario")
);

CREATE TABLE IF NOT EXISTS "detalle_pedido" (
	"id_detalle"	INTEGER,
	"id_pedido"	INTEGER NOT NULL,
	"id_producto"	INTEGER NOT NULL,
	"cantidad"	INTEGER NOT NULL CHECK("cantidad" > 0),
	"precio_unitario"	REAL NOT NULL CHECK("precio_unitario" > 0),
	"subtotal"	REAL NOT NULL CHECK("subtotal" >= 0),
	PRIMARY KEY("id_detalle" AUTOINCREMENT),
	FOREIGN KEY("id_pedido") REFERENCES "pedido"("id_pedido"),
	FOREIGN KEY("id_producto") REFERENCES "producto"("id_producto")
);

-- Pago: en la app (pasarela en modo de pruebas) o en efectivo en caja.
-- referencia es la que devuelve la pasarela; UNIQUE evita aprobar dos veces el mismo pago.
CREATE TABLE IF NOT EXISTS "pago" (
	"id_pago"	INTEGER,
	"id_pedido"	INTEGER NOT NULL,
	"id_usuario"	INTEGER,
	"metodo"	TEXT NOT NULL CHECK("metodo" IN ('app', 'efectivo')),
	"medio"	TEXT,
	"estado"	TEXT NOT NULL DEFAULT 'pendiente' CHECK("estado" IN ('pendiente', 'aprobado', 'rechazado')),
	"monto"	REAL NOT NULL CHECK("monto" > 0),
	"referencia"	TEXT UNIQUE,
	"fecha"	DATETIME NOT NULL DEFAULT (datetime('now','localtime')),
	PRIMARY KEY("id_pago" AUTOINCREMENT),
	FOREIGN KEY("id_pedido") REFERENCES "pedido"("id_pedido"),
	FOREIGN KEY("id_usuario") REFERENCES "usuario"("id_usuario")
);

-- Transaccion: registro de cada operación (trazabilidad), confirmada o revertida.
CREATE TABLE IF NOT EXISTS "transaccion" (
	"id_transaccion"	INTEGER,
	"id_pedido"	INTEGER NOT NULL,
	"id_usuario"	INTEGER,
	"tipo"	TEXT NOT NULL CHECK("tipo" IN ('registro_pedido', 'modificacion_pedido', 'cambio_estado', 'pago', 'cancelacion')),
	"fecha_hora"	DATETIME NOT NULL DEFAULT (datetime('now','localtime')),
	"resultado"	TEXT NOT NULL CHECK("resultado" IN ('confirmada', 'revertida')),
	"descripcion"	TEXT,
	PRIMARY KEY("id_transaccion" AUTOINCREMENT),
	FOREIGN KEY("id_pedido") REFERENCES "pedido"("id_pedido"),
	FOREIGN KEY("id_usuario") REFERENCES "usuario"("id_usuario")
);

-- Notificacion: aviso de pedido listo (web push o en la página de seguimiento).
CREATE TABLE IF NOT EXISTS "notificacion" (
	"id_notificacion"	INTEGER,
	"id_pedido"	INTEGER NOT NULL,
	"mensaje"	TEXT NOT NULL,
	"canal"	TEXT NOT NULL CHECK("canal" IN ('push', 'pagina')),
	"estado"	TEXT NOT NULL DEFAULT 'pendiente' CHECK("estado" IN ('pendiente', 'enviada', 'vista')),
	"fecha_envio"	DATETIME,
	PRIMARY KEY("id_notificacion" AUTOINCREMENT),
	FOREIGN KEY("id_pedido") REFERENCES "pedido"("id_pedido")
);

-- Índices para las consultas más frecuentes (cola del cajero, seguimiento y reportes).
CREATE INDEX IF NOT EXISTS "idx_pedido_estado" ON "pedido" ("estado");
CREATE INDEX IF NOT EXISTS "idx_pedido_fecha" ON "pedido" ("fecha_hora");
CREATE INDEX IF NOT EXISTS "idx_detalle_pedido" ON "detalle_pedido" ("id_pedido");
CREATE INDEX IF NOT EXISTS "idx_pago_pedido" ON "pago" ("id_pedido");
CREATE INDEX IF NOT EXISTS "idx_transaccion_pedido" ON "transaccion" ("id_pedido");
CREATE INDEX IF NOT EXISTS "idx_notificacion_pedido" ON "notificacion" ("id_pedido");

COMMIT;
