import re
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from models import database, Product, Order, OrderItem

application = Flask(__name__)
application.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
application.config['SECRET_KEY'] = 'ies-secure-key-123'
application.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
database.init_app(application)

# Read admin password from environment variable (fallback to 'admin123' for testing)
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# --- SECURITY GATE ---
@application.before_request
def restrict_admin_access():
    if request.path.startswith('/admin') and request.path != '/admin/login':
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))

# --- CUSTOMER ROUTES ---

@application.route('/')
def index():
    query = request.args.get('search', '')
    if query:
        all_products = Product.query.all()
        regex = re.compile(query, re.IGNORECASE)
        products = [p for p in all_products if regex.search(p.description or "") or regex.search(p.item_number)]
    else:
        products = Product.query.limit(20).all()
    return render_template('index.html', products=products)

@application.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    quantity = int(request.form.get('quantity', 1))
    product = Product.query.get_or_404(product_id)
    cart = session.get('cart', {})
    current_in_cart = cart.get(str(product_id), 0)

    if (current_in_cart + quantity) > product.in_stock:
        flash(f"Only {product.in_stock} available.", "danger")
    else:
        cart[str(product_id)] = current_in_cart + quantity
        session['cart'] = cart
        flash(f"Added {product.description} to cart.", "success")
    return redirect(url_for('index'))

@application.route('/update_cart/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    new_quantity = int(request.form.get('quantity', 1))
    product = Product.query.get_or_404(product_id)
    cart = session.get('cart', {})

    if new_quantity > product.in_stock:
        flash(f"Limit reached. Only {product.in_stock} in stock.", "danger")
        cart[str(product_id)] = int(product.in_stock)
    elif new_quantity <= 0:
        cart.pop(str(product_id), None)
    else:
        cart[str(product_id)] = new_quantity

    session['cart'] = cart
    return redirect(url_for('view_cart'))

@application.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    cart.pop(str(product_id), None)
    session['cart'] = cart
    return redirect(url_for('view_cart'))

@application.route('/cart', methods=['GET', 'POST'])
def view_cart():
    cart = session.get('cart', {})
    if request.method == 'POST':
        customer_name = request.form.get('name')
        if not customer_name or not cart:
            flash("Name required for order.", "danger")
            return redirect(url_for('view_cart'))

        new_order = Order(customer_name=customer_name, status='submitted')
        database.session.add(new_order)
        database.session.flush()

        for product_id, quantity in cart.items():
            product = Product.query.get(int(product_id))
            if product:
                product.in_stock -= int(quantity)
                order_item = OrderItem(order_id=new_order.id, product_id=product.id,
                                       product_name=product.description, quantity=int(quantity),
                                       price_per_unit=product.price)
                database.session.add(order_item)
        database.session.commit()
        session.pop('cart', None)
        return redirect(url_for('receipt', order_id=new_order.id))

    items = []
    grand_total = 0
    for product_id, quantity in cart.items():
        product = Product.query.get(int(product_id))
        if product:
            subtotal = product.price * int(quantity)
            grand_total += subtotal
            items.append({'product': product, 'quantity': quantity, 'subtotal': subtotal})
    return render_template('cart.html', items=items, grand_total=grand_total)

@application.route('/receipt/<int:order_id>')
def receipt(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('receipt.html', order=order)

# --- ADMIN ROUTES ---

@application.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash("Logged in to Admin.", "success")
            return redirect(url_for('admin_panel'))
        flash("Incorrect password.", "danger")
    return render_template('admin_login.html')

@application.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash("Logged out.", "info")
    return redirect(url_for('index'))

@application.route('/admin')
def admin_panel():
    submitted_orders = Order.query.filter_by(status='submitted').all()
    ready_orders = Order.query.filter_by(status='ready').all()
    completed_orders = Order.query.filter_by(status='completed').order_by(Order.id.desc()).limit(50).all()
    return render_template('admin.html', submitted=submitted_orders, ready=ready_orders, completed=completed_orders)

@application.route('/mark_ready/<int:order_id>')
def mark_ready(order_id):
    order = Order.query.get(order_id)
    if order:
        order.status = 'ready'
        database.session.commit()
    return redirect(url_for('admin_panel'))

@application.route('/mark_picked_up/<int:order_id>')
def mark_picked_up(order_id):
    order = Order.query.get(order_id)
    if order:
        order.status = 'completed'
        database.session.commit()
    return redirect(url_for('admin_panel'))

@application.route('/cancel_order/<int:order_id>')
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.status == 'submitted':
        for item in order.items:
            product = Product.query.get(item.product_id)
            if product:
                product.in_stock += item.quantity
        database.session.delete(order)
        database.session.commit()
        flash("Order cancelled.", "info")
        return redirect(url_for('index'))
    return redirect(url_for('receipt', order_id=order.id))

# --- NEW ADMIN ROUTES FOR REVERTING STATUS ---

@application.route('/move_to_submitted/<int:order_id>')
def move_to_submitted(order_id):
    order = Order.query.get_or_404(order_id)
    if order.status == 'ready':
        order.status = 'submitted'
        database.session.commit()
        flash(f"Order #{order.id} moved back to submitted.", "info")
    return redirect(url_for('admin_panel'))

@application.route('/move_to_ready/<int:order_id>')
def move_to_ready(order_id):
    order = Order.query.get_or_404(order_id)
    if order.status == 'completed':
        order.status = 'ready'
        database.session.commit()
        flash(f"Order #{order.id} moved back to ready for pickup.", "info")
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    application.run(debug=True)