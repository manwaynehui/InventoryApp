from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

database = SQLAlchemy()

class Product(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    item_number = database.Column(database.String(100), unique=True, nullable=False)
    description = database.Column(database.String(255))
    price = database.Column(database.Float)
    in_stock = database.Column(database.Float)

class Order(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    customer_name = database.Column(database.String(100), nullable=False)
    status = database.Column(database.String(20), default='submitted')
    created_at = database.Column(database.DateTime, default=datetime.now)  # ← changed from utcnow to now()
    items = database.relationship('OrderItem', backref='order', cascade="all, delete-orphan", lazy=True)

class OrderItem(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    order_id = database.Column(database.Integer, database.ForeignKey('order.id'), nullable=False)
    product_id = database.Column(database.Integer)
    product_name = database.Column(database.String(255))
    quantity = database.Column(database.Integer)
    price_per_unit = database.Column(database.Float)