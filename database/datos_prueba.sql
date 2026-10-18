-- =====================================================================
-- UBite - Datos iniciales de prueba
-- Se ejecuta después de schema.sql. Las fechas no se escriben a mano:
-- se calculan con la hora en que se ejecuta el script, restando unos
-- minutos a cada operación para que el historial quede en el orden en
-- que pasaría en la cafetería (cliente, pedido, pago, listo, entrega).
-- Cada pedido se registra como lo haría la aplicación: pedido, detalle,
-- descuento de stock y registro en transaccion dentro de una transacción.
--
-- Usuarios de prueba (solo para el entorno local):
--   cajero        -> usuario: acajero  / contraseña: Cajero2026*
--   administrador -> usuario: admin    / contraseña: Admin2026*
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- Datos básicos
-- ---------------------------------------------------------------------
BEGIN TRANSACTION;

INSERT INTO "usuario" ("nombre", "rol", "username", "password_hash") VALUES
 ('Ana Torres', 'cajero', 'acajero', 'scrypt:32768:8:1$NBBMK4VB5P2olwLg$f51019ebe3290a83f4d36d0084e9a67e6075185af2f04c580544334c9afaf40c2ea9419741495d39badeee98fbaf19af7340d1fd21fa410cd21d0a62e1f0c059'),
 ('Luis Gómez', 'administrador', 'admin', 'scrypt:32768:8:1$SSkTOC1QYaNWyhIM$5be104d577671fadc6d63d737ae425eb2a902d549f94d877b1b0f64151a37434586c83ccf19389bf819b9a968d95388e1dd2ff18d02d2a53950b3bfa85fdcc12');

INSERT INTO "categoria" ("nombre") VALUES ('Bebidas'), ('Snacks'), ('Comidas');

INSERT INTO "producto" ("nombre", "descripcion", "precio", "stock_actual", "stock_minimo", "id_categoria") VALUES
 ('Agua en botella', 'Botella de 600 ml', 2500, 30, 8, 1),
 ('Gaseosa', 'Botella de 400 ml', 3500, 24, 6, 1),
 ('Jugo en caja', 'Caja de 200 ml', 2500, 20, 6, 1),
 ('Papas fritas', 'Paquete individual', 2500, 25, 8, 2),
 ('Galletas', 'Paquete individual', 2000, 20, 5, 2),
 ('Chocolatina', 'Unidad', 2000, 15, 5, 2),
 ('Empanada', 'De carne, se calienta al pedir', 3000, 18, 5, 3),
 ('Sándwich de jamón y queso', 'Se calienta al pedir', 7000, 10, 3, 3),
 ('Pastel de pollo', 'Se calienta al pedir', 4000, 12, 4, 3);

INSERT INTO "cliente" ("nombre", "telefono", "fecha_registro") VALUES
 ('Camila Rojas', '3001234567', datetime('now','localtime','-46 minutes')),
 ('Andrés Pérez', '3109876543', datetime('now','localtime','-36 minutes')),
 ('Mateo Díaz', '3205551234', datetime('now','localtime','-31 minutes')),
 ('Laura Méndez', '3157778899', datetime('now','localtime','-21 minutes'));

COMMIT;

-- ---------------------------------------------------------------------
-- Pedido UB-0001: por QR, pagado en la app (Nequi, sandbox), ya está listo
-- 1 Papas fritas (2500) + 1 Gaseosa (3500) = 6000
-- ---------------------------------------------------------------------
BEGIN TRANSACTION;
INSERT INTO "pedido" ("codigo", "id_cliente", "origen", "total", "fecha_hora") VALUES ('UB-0001', 1, 'qr', 6000, datetime('now','localtime','-45 minutes'));
INSERT INTO "detalle_pedido" ("id_pedido", "id_producto", "cantidad", "precio_unitario", "subtotal") VALUES
 (1, 4, 1, 2500, 2500),
 (1, 2, 1, 3500, 3500);
UPDATE "producto" SET "stock_actual" = "stock_actual" - 1 WHERE "id_producto" IN (4, 2);
INSERT INTO "transaccion" ("id_pedido", "tipo", "resultado", "descripcion", "fecha_hora") VALUES
 (1, 'registro_pedido', 'confirmada', 'Pedido registrado por QR; stock descontado', datetime('now','localtime','-45 minutes'));
COMMIT;

BEGIN TRANSACTION;
INSERT INTO "pago" ("id_pedido", "metodo", "medio", "estado", "monto", "referencia", "fecha") VALUES
 (1, 'app', 'nequi', 'aprobado', 6000, 'SBX-NEQ-000001', datetime('now','localtime','-44 minutes'));
INSERT INTO "transaccion" ("id_pedido", "tipo", "resultado", "descripcion", "fecha_hora") VALUES
 (1, 'pago', 'confirmada', 'Pago aprobado por la pasarela (sandbox); pedido con prioridad', datetime('now','localtime','-44 minutes'));
COMMIT;

BEGIN TRANSACTION;
UPDATE "pedido" SET "estado" = 'listo' WHERE "id_pedido" = 1;
INSERT INTO "transaccion" ("id_pedido", "id_usuario", "tipo", "resultado", "descripcion", "fecha_hora") VALUES
 (1, 1, 'cambio_estado', 'confirmada', 'en_cola -> listo', datetime('now','localtime','-41 minutes'));
INSERT INTO "notificacion" ("id_pedido", "mensaje", "canal", "estado", "fecha_envio") VALUES
 (1, 'Tu pedido UB-0001 está listo. Ya está pago, solo acércate a recogerlo.', 'push', 'enviada', datetime('now','localtime','-41 minutes'));
COMMIT;

-- ---------------------------------------------------------------------
-- Pedido UB-0002: por QR, el pago en la app fue rechazado y el cliente
-- pagará en caja al recoger; sigue en cola
-- 2 Empanadas (3000) + 1 Jugo en caja (2500) = 8500
-- ---------------------------------------------------------------------
BEGIN TRANSACTION;
INSERT INTO "pedido" ("codigo", "id_cliente", "origen", "total", "fecha_hora") VALUES ('UB-0002', 2, 'qr', 8500, datetime('now','localtime','-35 minutes'));
INSERT INTO "detalle_pedido" ("id_pedido", "id_producto", "cantidad", "precio_unitario", "subtotal") VALUES
 (2, 7, 2, 3000, 6000),
 (2, 3, 1, 2500, 2500);
UPDATE "producto" SET "stock_actual" = "stock_actual" - 2 WHERE "id_producto" = 7;
UPDATE "producto" SET "stock_actual" = "stock_actual" - 1 WHERE "id_producto" = 3;
INSERT INTO "transaccion" ("id_pedido", "tipo", "resultado", "descripcion", "fecha_hora") VALUES
 (2, 'registro_pedido', 'confirmada', 'Pedido registrado por QR; stock descontado', datetime('now','localtime','-35 minutes'));
COMMIT;

BEGIN TRANSACTION;
INSERT INTO "pago" ("id_pedido", "metodo", "medio", "estado", "monto", "referencia", "fecha") VALUES
 (2, 'app', 'pse', 'rechazado', 8500, 'SBX-PSE-000002', datetime('now','localtime','-34 minutes'));
INSERT INTO "transaccion" ("id_pedido", "tipo", "resultado", "descripcion", "fecha_hora") VALUES
 (2, 'pago', 'revertida', 'Pago rechazado por la pasarela (sandbox); el pedido sigue en cola para pago en caja', datetime('now','localtime','-34 minutes'));
COMMIT;

-- ---------------------------------------------------------------------
-- Pedido UB-0003: presencial, registrado por el cajero, pagado en efectivo
-- y entregado
-- 1 Sándwich de jamón y queso (7000) = 7000
-- ---------------------------------------------------------------------
BEGIN TRANSACTION;
INSERT INTO "pedido" ("codigo", "id_cliente", "id_usuario", "origen", "total", "fecha_hora") VALUES ('UB-0003', 3, 1, 'presencial', 7000, datetime('now','localtime','-30 minutes'));
INSERT INTO "detalle_pedido" ("id_pedido", "id_producto", "cantidad", "precio_unitario", "subtotal") VALUES
 (3, 8, 1, 7000, 7000);
UPDATE "producto" SET "stock_actual" = "stock_actual" - 1 WHERE "id_producto" = 8;
INSERT INTO "transaccion" ("id_pedido", "id_usuario", "tipo", "resultado", "descripcion", "fecha_hora") VALUES
 (3, 1, 'registro_pedido', 'confirmada', 'Pedido presencial registrado por el cajero; stock descontado', datetime('now','localtime','-30 minutes'));
COMMIT;

BEGIN TRANSACTION;
UPDATE "pedido" SET "estado" = 'listo' WHERE "id_pedido" = 3;
INSERT INTO "transaccion" ("id_pedido", "id_usuario", "tipo", "resultado", "descripcion", "fecha_hora") VALUES
 (3, 1, 'cambio_estado', 'confirmada', 'en_cola -> listo', datetime('now','localtime','-27 minutes'));
INSERT INTO "notificacion" ("id_pedido", "mensaje", "canal", "estado", "fecha_envio") VALUES
 (3, 'Tu pedido UB-0003 está listo. Acércate a la caja para pagar y recogerlo.', 'pagina', 'vista', datetime('now','localtime','-27 minutes'));
COMMIT;

BEGIN TRANSACTION;
INSERT INTO "pago" ("id_pedido", "id_usuario", "metodo", "medio", "estado", "monto", "fecha") VALUES
 (3, 1, 'efectivo', 'efectivo', 'aprobado', 7000, datetime('now','localtime','-25 minutes'));
UPDATE "pedido" SET "estado" = 'entregado' WHERE "id_pedido" = 3;
INSERT INTO "transaccion" ("id_pedido", "id_usuario", "tipo", "resultado", "descripcion", "fecha_hora") VALUES
 (3, 1, 'pago', 'confirmada', 'Cobro en caja al entregar; listo -> entregado', datetime('now','localtime','-25 minutes'));
COMMIT;

-- ---------------------------------------------------------------------
-- Pedido UB-0004: por QR, cancelado por el cliente mientras estaba en cola
-- 1 Chocolatina (2000) = 2000; el stock se devuelve al cancelar
-- ---------------------------------------------------------------------
BEGIN TRANSACTION;
INSERT INTO "pedido" ("codigo", "id_cliente", "origen", "total", "fecha_hora") VALUES ('UB-0004', 4, 'qr', 2000, datetime('now','localtime','-20 minutes'));
INSERT INTO "detalle_pedido" ("id_pedido", "id_producto", "cantidad", "precio_unitario", "subtotal") VALUES
 (4, 6, 1, 2000, 2000);
UPDATE "producto" SET "stock_actual" = "stock_actual" - 1 WHERE "id_producto" = 6;
INSERT INTO "transaccion" ("id_pedido", "tipo", "resultado", "descripcion", "fecha_hora") VALUES
 (4, 'registro_pedido', 'confirmada', 'Pedido registrado por QR; stock descontado', datetime('now','localtime','-20 minutes'));
COMMIT;

BEGIN TRANSACTION;
UPDATE "pedido" SET "estado" = 'cancelado' WHERE "id_pedido" = 4;
UPDATE "producto" SET "stock_actual" = "stock_actual" + 1 WHERE "id_producto" = 6;
INSERT INTO "transaccion" ("id_pedido", "tipo", "resultado", "descripcion", "fecha_hora") VALUES
 (4, 'cancelacion', 'confirmada', 'Cancelado por el cliente en cola; stock devuelto', datetime('now','localtime','-17 minutes'));
COMMIT;
