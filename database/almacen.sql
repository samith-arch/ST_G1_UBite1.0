-- almacen de datos de UBite (ubite_dw.db): esquema en estrella para reportes, Power BI y la red neuronal.
-- no guarda nombres ni celulares; los clientes quedan con un identificador anonimo (hash).

CREATE TABLE IF NOT EXISTS dim_fecha (
    id_fecha        INTEGER PRIMARY KEY,          -- AAAAMMDD
    fecha           DATE NOT NULL UNIQUE,
    dia_semana      INTEGER NOT NULL CHECK (dia_semana BETWEEN 0 AND 6),   -- 0 = lunes
    nombre_dia      TEXT NOT NULL,
    semana_semestre INTEGER NOT NULL,
    periodo         TEXT NOT NULL,
    es_festivo      INTEGER NOT NULL CHECK (es_festivo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS dim_franja (
    id_franja   INTEGER PRIMARY KEY,              -- 0 = 00:00, 14 = 07:00, 47 = 23:30
    hora_inicio TEXT NOT NULL,
    hora_fin    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_producto (
    id_producto   INTEGER PRIMARY KEY,
    nombre        TEXT NOT NULL,
    categoria     TEXT NOT NULL,
    precio_actual REAL NOT NULL,
    activo        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS hecho_venta (
    id_venta     INTEGER PRIMARY KEY,
    id_pedido    INTEGER NOT NULL,
    id_fecha     INTEGER NOT NULL REFERENCES dim_fecha (id_fecha),
    id_franja    INTEGER NOT NULL REFERENCES dim_franja (id_franja),
    id_producto  INTEGER NOT NULL REFERENCES dim_producto (id_producto),
    origen       TEXT NOT NULL,
    metodo_pago  TEXT,
    cantidad     INTEGER NOT NULL CHECK (cantidad > 0),
    valor        REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS hecho_pedido (
    id_pedido            INTEGER PRIMARY KEY,
    id_fecha             INTEGER NOT NULL REFERENCES dim_fecha (id_fecha),
    id_franja            INTEGER NOT NULL REFERENCES dim_franja (id_franja),
    cliente_anonimo      TEXT NOT NULL,
    origen               TEXT NOT NULL,
    metodo_pago          TEXT,
    estado_final         TEXT NOT NULL,
    min_cola_a_listo     REAL,
    min_listo_a_entrega  REAL,
    total                REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS hecho_inventario (
    id_fecha          INTEGER NOT NULL REFERENCES dim_fecha (id_fecha),
    id_producto       INTEGER NOT NULL REFERENCES dim_producto (id_producto),
    stock_cierre      INTEGER NOT NULL,
    stock_minimo      INTEGER NOT NULL,
    unidades_vendidas INTEGER NOT NULL,
    PRIMARY KEY (id_fecha, id_producto)
);

CREATE TABLE IF NOT EXISTS prediccion_demanda (
    id_fecha            INTEGER NOT NULL REFERENCES dim_fecha (id_fecha),
    id_franja           INTEGER NOT NULL REFERENCES dim_franja (id_franja),
    id_producto         INTEGER NOT NULL REFERENCES dim_producto (id_producto),
    unidades_estimadas  REAL NOT NULL,
    modelo              TEXT NOT NULL,
    fecha_calculo       DATETIME NOT NULL,
    PRIMARY KEY (id_fecha, id_franja, id_producto)
);

CREATE TABLE IF NOT EXISTS etl_control (
    id_carga              INTEGER PRIMARY KEY,
    fecha_ejecucion       DATETIME NOT NULL,
    ultima_fecha_extraida DATE,
    filas_cargadas        INTEGER NOT NULL,
    resultado             TEXT NOT NULL,
    detalle               TEXT
);

CREATE INDEX IF NOT EXISTS ix_venta_fecha ON hecho_venta (id_fecha, id_franja, id_producto);
CREATE INDEX IF NOT EXISTS ix_pedido_fecha ON hecho_pedido (id_fecha);
