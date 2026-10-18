-- UBite - exportación de ubite.db (2026-10-17 21:30:36)
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
	"subtotal"	REAL NOT NULL CHECK("subtotal" >= 0),
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
INSERT INTO "cliente" VALUES (1,'Camila Rojas','3001234567','2026-10-17 20:44:36',NULL);
INSERT INTO "cliente" VALUES (2,'Andrés Pérez','3109876543','2026-10-17 20:54:36',NULL);
INSERT INTO "cliente" VALUES (3,'Mateo Díaz','3205551234','2026-10-17 20:59:36',NULL);
INSERT INTO "cliente" VALUES (4,'Laura Méndez','3157778899','2026-10-17 21:09:36',NULL);
INSERT INTO "usuario" VALUES (1,'Ana Torres','cajero','acajero','scrypt:32768:8:1$NBBMK4VB5P2olwLg$f51019ebe3290a83f4d36d0084e9a67e6075185af2f04c580544334c9afaf40c2ea9419741495d39badeee98fbaf19af7340d1fd21fa410cd21d0a62e1f0c059',1);
INSERT INTO "usuario" VALUES (2,'Luis Gómez','administrador','admin','scrypt:32768:8:1$SSkTOC1QYaNWyhIM$5be104d577671fadc6d63d737ae425eb2a902d549f94d877b1b0f64151a37434586c83ccf19389bf819b9a968d95388e1dd2ff18d02d2a53950b3bfa85fdcc12',1);
INSERT INTO "categoria" VALUES (1,'Bebidas');
INSERT INTO "categoria" VALUES (2,'Snacks');
INSERT INTO "categoria" VALUES (3,'Comidas');
INSERT INTO "producto" VALUES (1,'Agua en botella','Botella de 600 ml',2500.0,30,8,1,1);
INSERT INTO "producto" VALUES (2,'Gaseosa','Botella de 400 ml',3500.0,23,6,1,1);
INSERT INTO "producto" VALUES (3,'Jugo en caja','Caja de 200 ml',2500.0,19,6,1,1);
INSERT INTO "producto" VALUES (4,'Papas fritas','Paquete individual',2500.0,24,8,1,2);
INSERT INTO "producto" VALUES (5,'Galletas','Paquete individual',2000.0,20,5,1,2);
INSERT INTO "producto" VALUES (6,'Chocolatina','Unidad',2000.0,15,5,1,2);
INSERT INTO "producto" VALUES (7,'Empanada','De carne, se calienta al pedir',3000.0,16,5,1,3);
INSERT INTO "producto" VALUES (8,'Sándwich de jamón y queso','Se calienta al pedir',7000.0,9,3,1,3);
INSERT INTO "producto" VALUES (9,'Pastel de pollo','Se calienta al pedir',4000.0,12,4,1,3);
INSERT INTO "pedido" VALUES (1,'UB-0001',1,NULL,'2026-10-17 20:45:36','qr','listo',6000.0);
INSERT INTO "pedido" VALUES (2,'UB-0002',2,NULL,'2026-10-17 20:55:36','qr','en_cola',8500.0);
INSERT INTO "pedido" VALUES (3,'UB-0003',3,1,'2026-10-17 21:00:36','presencial','entregado',7000.0);
INSERT INTO "pedido" VALUES (4,'UB-0004',4,NULL,'2026-10-17 21:10:36','qr','cancelado',2000.0);
INSERT INTO "detalle_pedido" VALUES (1,1,4,1,2500.0,2500.0);
INSERT INTO "detalle_pedido" VALUES (2,1,2,1,3500.0,3500.0);
INSERT INTO "detalle_pedido" VALUES (3,2,7,2,3000.0,6000.0);
INSERT INTO "detalle_pedido" VALUES (4,2,3,1,2500.0,2500.0);
INSERT INTO "detalle_pedido" VALUES (5,3,8,1,7000.0,7000.0);
INSERT INTO "detalle_pedido" VALUES (6,4,6,1,2000.0,2000.0);
INSERT INTO "pago" VALUES (1,1,NULL,'app','nequi','aprobado',6000.0,'SBX-NEQ-000001','2026-10-17 20:46:36');
INSERT INTO "pago" VALUES (2,2,NULL,'app','pse','rechazado',8500.0,'SBX-PSE-000002','2026-10-17 20:56:36');
INSERT INTO "pago" VALUES (3,3,1,'efectivo','efectivo','aprobado',7000.0,NULL,'2026-10-17 21:05:36');
INSERT INTO "transaccion" VALUES (1,1,NULL,'registro_pedido','2026-10-17 20:45:36','confirmada','Pedido registrado por QR; stock descontado');
INSERT INTO "transaccion" VALUES (2,1,NULL,'pago','2026-10-17 20:46:36','confirmada','Pago aprobado por la pasarela (sandbox); pedido con prioridad');
INSERT INTO "transaccion" VALUES (3,1,1,'cambio_estado','2026-10-17 20:49:36','confirmada','en_cola -> listo');
INSERT INTO "transaccion" VALUES (4,2,NULL,'registro_pedido','2026-10-17 20:55:36','confirmada','Pedido registrado por QR; stock descontado');
INSERT INTO "transaccion" VALUES (5,2,NULL,'pago','2026-10-17 20:56:36','revertida','Pago rechazado por la pasarela (sandbox); el pedido sigue en cola para pago en caja');
INSERT INTO "transaccion" VALUES (6,3,1,'registro_pedido','2026-10-17 21:00:36','confirmada','Pedido presencial registrado por el cajero; stock descontado');
INSERT INTO "transaccion" VALUES (7,3,1,'cambio_estado','2026-10-17 21:03:36','confirmada','en_cola -> listo');
INSERT INTO "transaccion" VALUES (8,3,1,'pago','2026-10-17 21:05:36','confirmada','Cobro en caja al entregar; listo -> entregado');
INSERT INTO "transaccion" VALUES (9,4,NULL,'registro_pedido','2026-10-17 21:10:36','confirmada','Pedido registrado por QR; stock descontado');
INSERT INTO "transaccion" VALUES (10,4,NULL,'cancelacion','2026-10-17 21:13:36','confirmada','Cancelado por el cliente en cola; stock devuelto');
INSERT INTO "notificacion" VALUES (1,1,'Tu pedido UB-0001 está listo. Ya está pago, solo acércate a recogerlo.','push','enviada','2026-10-17 20:49:36');
INSERT INTO "notificacion" VALUES (2,3,'Tu pedido UB-0003 está listo. Acércate a la caja para pagar y recogerlo.','pagina','vista','2026-10-17 21:03:36');
CREATE INDEX IF NOT EXISTS "idx_detalle_pedido" ON "detalle_pedido" ("id_pedido");
CREATE INDEX IF NOT EXISTS "idx_notificacion_pedido" ON "notificacion" ("id_pedido");
CREATE INDEX IF NOT EXISTS "idx_pago_pedido" ON "pago" ("id_pedido");
CREATE INDEX IF NOT EXISTS "idx_pedido_estado" ON "pedido" ("estado");
CREATE INDEX IF NOT EXISTS "idx_pedido_fecha" ON "pedido" ("fecha_hora");
CREATE INDEX IF NOT EXISTS "idx_transaccion_pedido" ON "transaccion" ("id_pedido");
COMMIT;
