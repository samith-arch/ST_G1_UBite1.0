BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "categoria" (
	"id_categoria"	INTEGER,
	"nombre"	TEXT NOT NULL UNIQUE,
	PRIMARY KEY("id_categoria" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "cliente" (
	"id_cliente"	INTEGER,
	"nombre"	TEXT NOT NULL,
	"telefono"	TEXT,
	"email"	TEXT UNIQUE,
	"fecha_registro"	DATETIME DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY("id_cliente" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "detalle_pedido" (
	"id_detalle"	INTEGER,
	"id_pedido"	INTEGER NOT NULL,
	"id_producto"	INTEGER NOT NULL,
	"cantidad"	INTEGER NOT NULL CHECK("cantidad" > 0),
	"precio_unitario"	REAL NOT NULL CHECK("precio_unitario" >= 0),
	"subtotal"	REAL NOT NULL CHECK("subtotal" >= 0),
	PRIMARY KEY("id_detalle" AUTOINCREMENT),
	FOREIGN KEY("id_pedido") REFERENCES "pedido"("id_pedido"),
	FOREIGN KEY("id_producto") REFERENCES "producto"("id_producto")
);
CREATE TABLE IF NOT EXISTS "insumo" (
	"id_insumo"	INTEGER,
	"nombre"	TEXT NOT NULL,
	"unidad_medida"	TEXT NOT NULL,
	"stock_actual"	REAL NOT NULL DEFAULT 0 CHECK("stock_actual" >= 0),
	"stock_minimo"	REAL NOT NULL DEFAULT 0,
	PRIMARY KEY("id_insumo" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "pedido" (
	"id_pedido"	INTEGER,
	"id_cliente"	INTEGER NOT NULL,
	"id_usuario"	INTEGER,
	"fecha_hora"	DATETIME DEFAULT CURRENT_TIMESTAMP,
	"estado"	TEXT NOT NULL DEFAULT 'pendiente' CHECK("estado" IN ('pendiente', 'listo', 'entregado', 'cancelado')),
	"total"	REAL NOT NULL DEFAULT 0 CHECK("total" >= 0),
	PRIMARY KEY("id_pedido" AUTOINCREMENT),
	FOREIGN KEY("id_cliente") REFERENCES "cliente"("id_cliente"),
	FOREIGN KEY("id_usuario") REFERENCES "usuario"("id_usuario")
);
CREATE TABLE IF NOT EXISTS "producto" (
	"id_producto"	INTEGER,
	"nombre"	TEXT NOT NULL,
	"descripcion"	TEXT,
	"precio"	REAL NOT NULL CHECK("precio" >= 0),
	"id_categoria"	INTEGER NOT NULL,
	"disponible"	BOOLEAN NOT NULL DEFAULT 1,
	PRIMARY KEY("id_producto" AUTOINCREMENT),
	FOREIGN KEY("id_categoria") REFERENCES "categoria"("id_categoria")
);
CREATE TABLE IF NOT EXISTS "producto_insumo" (
	"id_producto"	INTEGER NOT NULL,
	"id_insumo"	INTEGER NOT NULL,
	"cantidad_requerida"	REAL NOT NULL CHECK("cantidad_requerida" > 0),
	PRIMARY KEY("id_producto","id_insumo"),
	FOREIGN KEY("id_insumo") REFERENCES "insumo"("id_insumo"),
	FOREIGN KEY("id_producto") REFERENCES "producto"("id_producto")
);
CREATE TABLE IF NOT EXISTS "usuario" (
	"id_usuario"	INTEGER,
	"nombre"	TEXT NOT NULL,
	"rol"	TEXT NOT NULL CHECK("rol" IN ('cajero', 'administrador')),
	"username"	TEXT NOT NULL UNIQUE,
	"password_hash"	TEXT NOT NULL,
	PRIMARY KEY("id_usuario" AUTOINCREMENT)
);
INSERT INTO "categoria" VALUES (1,'Bebidas');
INSERT INTO "categoria" VALUES (2,'Comidas');
INSERT INTO "categoria" VALUES (3,'Snacks');
INSERT INTO "cliente" VALUES (1,'Camila Rojas','3001234567','camila.rojas@umb.edu.co','2026-09-22 03:22:15');
INSERT INTO "cliente" VALUES (2,'Andrés Pérez','3109876543','andres.perez@umb.edu.co','2026-09-22 03:22:15');
INSERT INTO "detalle_pedido" VALUES (1,1,1,1,4500.0,4500.0);
INSERT INTO "insumo" VALUES (1,'Café molido','g',5000.0,500.0);
INSERT INTO "insumo" VALUES (2,'Leche','ml',8000.0,1000.0);
INSERT INTO "insumo" VALUES (3,'Pan','unidad',50.0,10.0);
INSERT INTO "pedido" VALUES (1,1,1,'2026-09-22 03:22:33','pendiente',4500.0);
INSERT INTO "producto" VALUES (1,'Café con leche','Café tradicional con leche caliente',4500.0,1,1);
INSERT INTO "producto" VALUES (2,'Sándwich de jamón','Pan con jamón y queso',8000.0,2,1);
INSERT INTO "producto_insumo" VALUES (1,1,15.0);
INSERT INTO "producto_insumo" VALUES (1,2,150.0);
INSERT INTO "producto_insumo" VALUES (2,3,2.0);
INSERT INTO "usuario" VALUES (1,'Ana Torres','cajero','atorres','hash_temporal_1');
INSERT INTO "usuario" VALUES (2,'Luis Gómez','administrador','lgomez','hash_temporal_2');
COMMIT;
