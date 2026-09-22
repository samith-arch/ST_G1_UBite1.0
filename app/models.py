from datetime import datetime
from .database import db


class Cliente(db.Model):
    __tablename__ = "cliente"

    id_cliente = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.Text, nullable=False)
    telefono = db.Column(db.Text)
    email = db.Column(db.Text, unique=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    pedidos = db.relationship("Pedido", backref="cliente", lazy=True)


class Usuario(db.Model):
    __tablename__ = "usuario"

    id_usuario = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.Text, nullable=False)
    rol = db.Column(db.Text, nullable=False)  # 'cajero' o 'administrador'
    username = db.Column(db.Text, nullable=False, unique=True)
    password_hash = db.Column(db.Text, nullable=False)

    pedidos = db.relationship("Pedido", backref="usuario", lazy=True)


class Categoria(db.Model):
    __tablename__ = "categoria"

    id_categoria = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.Text, nullable=False, unique=True)

    productos = db.relationship("Producto", backref="categoria", lazy=True)


class Producto(db.Model):
    __tablename__ = "producto"

    id_producto = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.Text, nullable=False)
    descripcion = db.Column(db.Text)
    precio = db.Column(db.Float, nullable=False)
    id_categoria = db.Column(db.Integer, db.ForeignKey("categoria.id_categoria"), nullable=False)
    disponible = db.Column(db.Boolean, nullable=False, default=True)

    insumos = db.relationship("ProductoInsumo", backref="producto", lazy=True)


class Insumo(db.Model):
    __tablename__ = "insumo"

    id_insumo = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.Text, nullable=False)
    unidad_medida = db.Column(db.Text, nullable=False)
    stock_actual = db.Column(db.Float, nullable=False, default=0)
    stock_minimo = db.Column(db.Float, nullable=False, default=0)

    productos = db.relationship("ProductoInsumo", backref="insumo", lazy=True)


class ProductoInsumo(db.Model):
    __tablename__ = "producto_insumo"

    id_producto = db.Column(db.Integer, db.ForeignKey("producto.id_producto"), primary_key=True)
    id_insumo = db.Column(db.Integer, db.ForeignKey("insumo.id_insumo"), primary_key=True)
    cantidad_requerida = db.Column(db.Float, nullable=False)


class Pedido(db.Model):
    __tablename__ = "pedido"

    id_pedido = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_cliente = db.Column(db.Integer, db.ForeignKey("cliente.id_cliente"), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey("usuario.id_usuario"))
    fecha_hora = db.Column(db.DateTime, default=datetime.utcnow)
    estado = db.Column(db.Text, nullable=False, default="pendiente")
    total = db.Column(db.Float, nullable=False, default=0)

    detalles = db.relationship("DetallePedido", backref="pedido", lazy=True)


class DetallePedido(db.Model):
    __tablename__ = "detalle_pedido"

    id_detalle = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_pedido = db.Column(db.Integer, db.ForeignKey("pedido.id_pedido"), nullable=False)
    id_producto = db.Column(db.Integer, db.ForeignKey("producto.id_producto"), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
