-- UBite - exportación de ubite.db (2026-11-06 00:18:33)
BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "cliente" (
	"id_cliente"	INTEGER,
	"nombre"	TEXT NOT NULL,
	"telefono"	TEXT NOT NULL,
	"fecha_registro"	DATETIME NOT NULL DEFAULT (datetime('now','localtime')),
	"suscripcion_push"	TEXT,
	PRIMARY KEY("id_cliente" AUTOINCREMENT)
);
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
	"subtotal"	REAL NOT NULL CHECK("subtotal" = "cantidad" * "precio_unitario"),
	PRIMARY KEY("id_detalle" AUTOINCREMENT),
	FOREIGN KEY("id_pedido") REFERENCES "pedido"("id_pedido"),
	FOREIGN KEY("id_producto") REFERENCES "producto"("id_producto")
);
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
INSERT INTO "cliente" VALUES (1,'Camila Rojas','3001234567','2026-11-05 23:32:32',NULL);
INSERT INTO "cliente" VALUES (2,'Andrés Pérez','3109876543','2026-11-05 23:42:32',NULL);
INSERT INTO "cliente" VALUES (3,'Mateo Díaz','3205551234','2026-11-05 23:47:32',NULL);
INSERT INTO "cliente" VALUES (4,'Laura Méndez','3157778899','2026-11-05 23:57:32',NULL);
INSERT INTO "usuario" VALUES (1,'Ana Torres','cajero','acajero','scrypt:32768:8:1$FfB1dwxePkRDXqfi$102097d43b076e67717f5f704419aa3b557fa7168fdb83394635897d0dccad981e71f2b5aa79d6dcae8b0c8f237157f73849f60d21533dde546f2d462689f013',1);
INSERT INTO "usuario" VALUES (2,'Luis Gómez','administrador','admin','scrypt:32768:8:1$6fHvan8J1fmNtfDG$2116f2e6f93bd577c99c8b8a9f3933ef220cfec5943a28cfcdb48bbeac2a22a03adf4a23f441f8444238b206cd7af524b3f11ce73c2aaa4ae47c1001eb7cdd8f',1);
INSERT INTO "categoria" VALUES (1,'Bebidas');
INSERT INTO "categoria" VALUES (2,'Snacks');
INSERT INTO "categoria" VALUES (3,'Comidas');
INSERT INTO "categoria" VALUES (4,'Panadería');
INSERT INTO "producto" VALUES (1,'Agua en botella','Botella de 600 ml',2500.0,30,8,1,1);
INSERT INTO "producto" VALUES (2,'Gaseosa','Botella de 400 ml',3500.0,23,6,1,1);
INSERT INTO "producto" VALUES (3,'Jugo en caja','Caja de 200 ml',2500.0,19,6,1,1);
INSERT INTO "producto" VALUES (4,'Papas fritas','Paquete individual',2500.0,24,8,1,2);
INSERT INTO "producto" VALUES (5,'Galletas','Paquete individual',2000.0,20,5,1,2);
INSERT INTO "producto" VALUES (6,'Chocolatina','Unidad',2000.0,15,5,1,2);
INSERT INTO "producto" VALUES (7,'Empanada','De carne, se calienta al pedir',3000.0,16,5,1,3);
INSERT INTO "producto" VALUES (8,'Sándwich de jamón y queso','Se calienta al pedir',7000.0,9,3,1,3);
INSERT INTO "producto" VALUES (9,'Pastel de pollo','Se calienta al pedir',4000.0,12,4,1,3);
INSERT INTO "producto" VALUES (10,'Té frío','Botella de 400 ml, sabor limón o durazno',3500.0,20,6,1,1);
INSERT INTO "producto" VALUES (11,'Bebida energizante','Lata de 250 ml',5000.0,15,4,1,1);
INSERT INTO "producto" VALUES (12,'Malta','Botella de 330 ml',3000.0,18,5,1,1);
INSERT INTO "producto" VALUES (13,'Bebida hidratante','Botella de 500 ml',4500.0,15,4,1,1);
INSERT INTO "producto" VALUES (14,'Avena en vaso','Vaso de 250 ml, fría',3500.0,15,4,1,1);
INSERT INTO "producto" VALUES (15,'Gaseosa personal','Lata de 330 ml',3000.0,20,6,1,1);
INSERT INTO "producto" VALUES (16,'Maní salado','Paquete individual',2000.0,20,5,1,2);
INSERT INTO "producto" VALUES (17,'Chicharrón en paquete','Paquete individual',3000.0,15,4,1,2);
INSERT INTO "producto" VALUES (18,'Platanitos','Paquete individual de plátano verde',2500.0,20,5,1,2);
INSERT INTO "producto" VALUES (19,'Barra de cereal','Unidad',2000.0,20,5,1,2);
INSERT INTO "producto" VALUES (20,'Chupeta','Unidad',500.0,40,10,1,2);
INSERT INTO "producto" VALUES (21,'Papa rellena','De carne y arroz, se calienta al pedir',4500.0,12,4,1,3);
INSERT INTO "producto" VALUES (22,'Arepa de queso','Se calienta al pedir',4000.0,12,4,1,3);
INSERT INTO "producto" VALUES (23,'Arepa rellena de pollo','Se calienta al pedir',6000.0,10,3,1,3);
INSERT INTO "producto" VALUES (24,'Pandebono','Unidad',2500.0,20,6,1,4);
INSERT INTO "producto" VALUES (25,'Almojábana','Unidad',2500.0,18,5,1,4);
INSERT INTO "producto" VALUES (26,'Buñuelo','Unidad',2000.0,20,6,1,4);
INSERT INTO "producto" VALUES (27,'Pastel de arequipe','Unidad',3500.0,12,4,1,4);
INSERT INTO "pedido" VALUES (1,'A-001',1,NULL,'2026-11-05 23:33:32','qr','listo',6000.0);
INSERT INTO "pedido" VALUES (2,'A-002',2,NULL,'2026-11-05 23:43:32','qr','en_cola',8500.0);
INSERT INTO "pedido" VALUES (3,'P-001',3,1,'2026-11-05 23:48:32','presencial','entregado',7000.0);
INSERT INTO "pedido" VALUES (4,'A-003',4,NULL,'2026-11-05 23:58:33','qr','cancelado',2000.0);
INSERT INTO "detalle_pedido" VALUES (1,1,4,1,2500.0,2500.0);
INSERT INTO "detalle_pedido" VALUES (2,1,2,1,3500.0,3500.0);
INSERT INTO "detalle_pedido" VALUES (3,2,7,2,3000.0,6000.0);
INSERT INTO "detalle_pedido" VALUES (4,2,3,1,2500.0,2500.0);
INSERT INTO "detalle_pedido" VALUES (5,3,8,1,7000.0,7000.0);
INSERT INTO "detalle_pedido" VALUES (6,4,6,1,2000.0,2000.0);
INSERT INTO "pago" VALUES (1,1,NULL,'app','nequi','aprobado',6000.0,'SBX-NEQ-000001','2026-11-05 23:34:32');
INSERT INTO "pago" VALUES (2,2,NULL,'app','pse','rechazado',8500.0,'SBX-PSE-000002','2026-11-05 23:44:32');
INSERT INTO "pago" VALUES (3,3,1,'efectivo','efectivo','aprobado',7000.0,NULL,'2026-11-05 23:48:32');
INSERT INTO "transaccion" VALUES (1,1,NULL,'registro_pedido','2026-11-05 23:33:32','confirmada','Pedido registrado por QR; stock descontado');
INSERT INTO "transaccion" VALUES (2,1,NULL,'pago','2026-11-05 23:34:32','confirmada','Pago aprobado por la pasarela (pruebas); pedido con prioridad');
INSERT INTO "transaccion" VALUES (3,1,1,'cambio_estado','2026-11-05 23:37:32','confirmada','en_cola -> listo');
INSERT INTO "transaccion" VALUES (4,2,NULL,'registro_pedido','2026-11-05 23:43:32','confirmada','Pedido registrado por QR; stock descontado');
INSERT INTO "transaccion" VALUES (5,2,NULL,'pago','2026-11-05 23:44:32','revertida','Pago rechazado por la pasarela (pruebas); paga en caja al recoger');
INSERT INTO "transaccion" VALUES (6,3,1,'registro_pedido','2026-11-05 23:48:32','confirmada','Pedido presencial registrado; stock descontado');
INSERT INTO "transaccion" VALUES (7,3,1,'pago','2026-11-05 23:48:32','confirmada','Cobro en caja al registrar el pedido');
INSERT INTO "transaccion" VALUES (8,3,1,'cambio_estado','2026-11-05 23:51:32','confirmada','en_preparacion -> listo');
INSERT INTO "transaccion" VALUES (9,3,1,'cambio_estado','2026-11-05 23:53:33','confirmada','listo -> entregado');
INSERT INTO "transaccion" VALUES (10,4,NULL,'registro_pedido','2026-11-05 23:58:33','confirmada','Pedido registrado por QR; stock descontado');
INSERT INTO "transaccion" VALUES (11,4,NULL,'cancelacion','2026-11-06 00:01:33','confirmada','Cancelado por el cliente en cola; stock devuelto');
INSERT INTO "notificacion" VALUES (1,1,'Tu pedido A-001 está listo. Ya está pago, solo acércate a recogerlo.','push','enviada','2026-11-05 23:37:32');
INSERT INTO "notificacion" VALUES (2,3,'Tu pedido P-001 está listo. Ya está pago, solo acércate a recogerlo.','pagina','vista','2026-11-05 23:51:33');
CREATE INDEX IF NOT EXISTS "idx_detalle_pedido" ON "detalle_pedido" ("id_pedido");
CREATE INDEX IF NOT EXISTS "idx_notificacion_pedido" ON "notificacion" ("id_pedido");
CREATE INDEX IF NOT EXISTS "idx_pago_pedido" ON "pago" ("id_pedido");
CREATE INDEX IF NOT EXISTS "idx_pedido_estado" ON "pedido" ("estado");
CREATE INDEX IF NOT EXISTS "idx_pedido_fecha" ON "pedido" ("fecha_hora");
CREATE INDEX IF NOT EXISTS "idx_transaccion_pedido" ON "transaccion" ("id_pedido");
CREATE UNIQUE INDEX IF NOT EXISTS "ux_pago_aprobado" ON "pago" ("id_pedido") WHERE "estado" = 'aprobado';
CREATE TRIGGER IF NOT EXISTS "trg_pedido_estado"
BEFORE UPDATE OF "estado" ON "pedido"
WHEN NEW."estado" <> OLD."estado" AND NOT (
	(OLD."estado" = 'en_cola' AND NEW."estado" IN ('en_preparacion', 'listo', 'cancelado')) OR
	(OLD."estado" = 'en_preparacion' AND NEW."estado" IN ('listo', 'cancelado')) OR
	(OLD."estado" = 'listo' AND NEW."estado" IN ('entregado', 'cancelado'))
)
BEGIN
	SELECT RAISE(ABORT, 'cambio de estado no permitido');
END;
COMMIT;
