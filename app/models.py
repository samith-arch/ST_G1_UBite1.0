# modelos, uno por cada tabla de database/schema.sql
from datetime import datetime

from flask_login import UserMixin

from .database import db


def ahora():
    return datetime.now().replace(microsecond=0)


class Cliente(db.Model):
    __tablename__ = "cliente"

    id_cliente = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.Text, nullable=False)
    telefono = db.Column(db.Text, nullable=False)
    fecha_registro = db.Column(db.DateTime, nullable=False, default=ahora)
    suscripcion_push = db.Column(db.Text)

    pedidos = db.relationship("Pedido", back_populates="cliente", lazy=True)


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuario"
    __table_args__ = (
        db.CheckConstraint("rol IN ('cajero', 'administrador')", name="ck_usuario_rol"),
    )

    id_usuario = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.Text, nullable=False)
    rol = db.Column(db.Text, nullable=False)
    username = db.Column(db.Text, nullable=False, unique=True)
    password_hash = db.Column(db.Text, nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)

    def get_id(self):
        return str(self.id_usuario)

    @property
    def is_active(self):
        return bool(self.activo)


class Categoria(db.Model):
    __tablename__ = "categoria"

    id_categoria = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.Text, nullable=False, unique=True)

    productos = db.relationship("Producto", back_populates="categoria", lazy=True)


class Producto(db.Model):
    __tablename__ = "producto"
    __table_args__ = (
        db.CheckConstraint("precio > 0", name="ck_producto_precio"),
        db.CheckConstraint("stock_actual >= 0", name="ck_producto_stock"),
        db.CheckConstraint("stock_minimo >= 0", name="ck_producto_minimo"),
    )

    id_producto = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.Text, nullable=False)
    descripcion = db.Column(db.Text)
    precio = db.Column(db.Float, nullable=False)
    stock_actual = db.Column(db.Integer, nullable=False, default=0)
    stock_minimo = db.Column(db.Integer, nullable=False, default=0)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    id_categoria = db.Column(db.Integer, db.ForeignKey("categoria.id_categoria"), nullable=False)

    categoria = db.relationship("Categoria", back_populates="productos")

    def validar_stock(self, cantidad):
        return self.activo and self.stock_actual >= cantidad

    def descontar_stock(self, cantidad):
        if not self.validar_stock(cantidad):
            raise ValueError(f"No hay stock suficiente de {self.nombre}")
        self.stock_actual -= cantidad

    def devolver_stock(self, cantidad):
        self.stock_actual += cantidad


class Pedido(db.Model):
    __tablename__ = "pedido"
    __table_args__ = (
        db.CheckConstraint("origen IN ('qr', 'presencial')", name="ck_pedido_origen"),
        db.CheckConstraint(
            "estado IN ('en_cola', 'en_preparacion', 'listo', 'entregado', 'cancelado')",
            name="ck_pedido_estado"),
        db.CheckConstraint("total >= 0", name="ck_pedido_total"),
    )

    # estados a los que puede pasar un pedido
    TRANSICIONES = {
        "en_cola": {"en_preparacion", "listo", "cancelado"},
        "en_preparacion": {"listo", "cancelado"},
        "listo": {"entregado", "cancelado"},
        "entregado": set(),
        "cancelado": set(),
    }

    id_pedido = db.Column(db.Integer, primary_key=True, autoincrement=True)
    codigo = db.Column(db.Text, nullable=False, unique=True)
    id_cliente = db.Column(db.Integer, db.ForeignKey("cliente.id_cliente"), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey("usuario.id_usuario"))
    fecha_hora = db.Column(db.DateTime, nullable=False, default=ahora)
    origen = db.Column(db.Text, nullable=False)
    estado = db.Column(db.Text, nullable=False, default="en_cola")
    total = db.Column(db.Float, nullable=False, default=0)

    cliente = db.relationship("Cliente", back_populates="pedidos")
    usuario = db.relationship("Usuario")
    detalles = db.relationship("DetallePedido", back_populates="pedido", lazy=True,
                               cascade="all, delete-orphan")
    pagos = db.relationship("Pago", back_populates="pedido", lazy=True)
    transacciones = db.relationship("Transaccion", back_populates="pedido", lazy=True)
    notificaciones = db.relationship("Notificacion", back_populates="pedido", lazy=True)

    def calcular_total(self):
        self.total = sum(d.subtotal for d in self.detalles)
        return self.total

    def cambiar_estado(self, nuevo):
        if nuevo not in self.TRANSICIONES[self.estado]:
            raise ValueError(f"No se puede pasar de {self.estado} a {nuevo}")
        self.estado = nuevo

    @property
    def pagado(self):
        return any(p.estado == "aprobado" for p in self.pagos)


class DetallePedido(db.Model):
    __tablename__ = "detalle_pedido"
    __table_args__ = (
        db.CheckConstraint("cantidad > 0", name="ck_detalle_cantidad"),
        db.CheckConstraint("precio_unitario > 0", name="ck_detalle_precio"),
        db.CheckConstraint("subtotal >= 0", name="ck_detalle_subtotal"),
    )

    id_detalle = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_pedido = db.Column(db.Integer, db.ForeignKey("pedido.id_pedido"), nullable=False)
    id_producto = db.Column(db.Integer, db.ForeignKey("producto.id_producto"), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

    pedido = db.relationship("Pedido", back_populates="detalles")
    producto = db.relationship("Producto")


class Pago(db.Model):
    __tablename__ = "pago"
    __table_args__ = (
        db.CheckConstraint("metodo IN ('app', 'efectivo')", name="ck_pago_metodo"),
        db.CheckConstraint("estado IN ('pendiente', 'aprobado', 'rechazado')", name="ck_pago_estado"),
        db.CheckConstraint("monto > 0", name="ck_pago_monto"),
    )

    id_pago = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_pedido = db.Column(db.Integer, db.ForeignKey("pedido.id_pedido"), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey("usuario.id_usuario"))
    metodo = db.Column(db.Text, nullable=False)
    medio = db.Column(db.Text)
    estado = db.Column(db.Text, nullable=False, default="pendiente")
    monto = db.Column(db.Float, nullable=False)
    referencia = db.Column(db.Text, unique=True)
    fecha = db.Column(db.DateTime, nullable=False, default=ahora)

    pedido = db.relationship("Pedido", back_populates="pagos")
    usuario = db.relationship("Usuario")

    def aprobar(self, referencia=None):
        self.estado = "aprobado"
        if referencia:
            self.referencia = referencia


class Transaccion(db.Model):
    __tablename__ = "transaccion"
    __table_args__ = (
        db.CheckConstraint(
            "tipo IN ('registro_pedido', 'modificacion_pedido', 'cambio_estado', 'pago', 'cancelacion')",
            name="ck_transaccion_tipo"),
        db.CheckConstraint("resultado IN ('confirmada', 'revertida')", name="ck_transaccion_resultado"),
    )

    id_transaccion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_pedido = db.Column(db.Integer, db.ForeignKey("pedido.id_pedido"), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey("usuario.id_usuario"))
    tipo = db.Column(db.Text, nullable=False)
    fecha_hora = db.Column(db.DateTime, nullable=False, default=ahora)
    resultado = db.Column(db.Text, nullable=False)
    descripcion = db.Column(db.Text)

    pedido = db.relationship("Pedido", back_populates="transacciones")
    usuario = db.relationship("Usuario")

    @classmethod
    def registrar(cls, pedido, tipo, resultado="confirmada", usuario=None, descripcion=None):
        t = cls(pedido=pedido, tipo=tipo, resultado=resultado,
                id_usuario=usuario.id_usuario if usuario else None,
                descripcion=descripcion)
        db.session.add(t)
        return t


class Notificacion(db.Model):
    __tablename__ = "notificacion"
    __table_args__ = (
        db.CheckConstraint("canal IN ('push', 'pagina')", name="ck_notificacion_canal"),
        db.CheckConstraint("estado IN ('pendiente', 'enviada', 'vista')", name="ck_notificacion_estado"),
    )

    id_notificacion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_pedido = db.Column(db.Integer, db.ForeignKey("pedido.id_pedido"), nullable=False)
    mensaje = db.Column(db.Text, nullable=False)
    canal = db.Column(db.Text, nullable=False)
    estado = db.Column(db.Text, nullable=False, default="pendiente")
    fecha_envio = db.Column(db.DateTime)

    pedido = db.relationship("Pedido", back_populates="notificaciones")
