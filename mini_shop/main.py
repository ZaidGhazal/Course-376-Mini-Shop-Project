"""Flask routes for the server-rendered customer and admin pages."""

import os
import secrets
from datetime import timedelta
from decimal import Decimal

from flask import (
    Flask,
    abort,
    flash,
    g,
    get_flashed_messages,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from pydantic import ValidationError
from sqlalchemy import select

from .database import SessionLocal
from .models import Admin, Category, Order, OrderItem, Product
from .schemas import CheckoutForm, ProductForm


app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static",
)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-me"),
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,  # Change to True when deployed with HTTPS.
)


def get_db():
    """Open one database session for the current web request."""
    if "database" not in g:
        g.database = SessionLocal()
    return g.database


@app.teardown_appcontext
def close_db(error=None):
    database = g.pop("database", None)
    if database is not None:
        database.close()


@app.before_request
def prepare_session():
    session.permanent = True
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)


@app.context_processor
def shared_page_values():
    messages = [
        {"category": category, "text": text}
        for category, text in get_flashed_messages(with_categories=True)
    ]
    return {
        "csrf_token": session.get("csrf_token", ""),
        "messages": messages,
        "cart_count": sum(session.get("cart", {}).values()),
        "current_admin": session.get("admin_username"),
    }


def check_csrf():
    saved_token = session.get("csrf_token", "")
    submitted_token = request.form.get("csrf_token", "")
    if not saved_token or not secrets.compare_digest(saved_token, submitted_token):
        abort(400, description="Invalid form security token")


def require_admin():
    if "admin_id" not in session:
        flash("Please log in as an administrator.", "danger")
        return redirect(url_for("admin_login"), code=303)
    return None


def find_or_404(model, item_id):
    item = get_db().get(model, item_id)
    if item is None:
        abort(404)
    return item


def cart_rows():
    saved_cart = session.get("cart", {})
    product_ids = [int(product_id) for product_id in saved_cart]
    products = (
        get_db().scalars(select(Product).where(Product.id.in_(product_ids))).all()
        if product_ids
        else []
    )
    rows = []
    for product in products:
        quantity = int(saved_cart.get(str(product.id), 0))
        if quantity > 0:
            rows.append(
                {
                    "product": product,
                    "quantity": quantity,
                    "line_total": product.price * quantity,
                }
            )
    return rows


@app.route("/api/health")
def health_check():
    return {"status": "ok"}


@app.route("/")
def catalog():
    # TODO (Milestone 4): add search, category filtering, sorting, and pagination.
    products = get_db().scalars(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.name)
    ).all()
    return render_template("catalog.html", products=products)


@app.route("/products/<int:product_id>")
def product_detail(product_id):
    product = find_or_404(Product, product_id)
    if not product.is_active:
        abort(404)
    return render_template("product_detail.html", product=product)


@app.route("/cart/items/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    check_csrf()
    product = find_or_404(Product, product_id)
    if not product.is_active:
        abort(404)
    cart = session.get("cart", {})
    key = str(product.id)
    cart[key] = int(cart.get(key, 0)) + 1
    session["cart"] = cart
    flash(f"Added {product.name} to your cart.", "success")
    return redirect(request.referrer or url_for("catalog"), code=303)


@app.route("/cart")
def view_cart():
    rows = cart_rows()
    total = sum((row["line_total"] for row in rows), Decimal("0.00"))
    return render_template("cart.html", rows=rows, total=total)


@app.route("/cart/items/<int:product_id>/remove", methods=["POST"])
def remove_from_cart(product_id):
    check_csrf()
    cart = session.get("cart", {})
    cart.pop(str(product_id), None)
    session["cart"] = cart
    flash("Item removed from the cart.", "success")
    return redirect(url_for("view_cart"), code=303)


@app.route("/checkout")
def checkout_page():
    rows = cart_rows()
    if not rows:
        flash("Your cart is empty.", "danger")
        return redirect(url_for("view_cart"), code=303)
    total = sum((row["line_total"] for row in rows), Decimal("0.00"))
    return render_template("checkout.html", rows=rows, total=total, form={}, errors=[])


@app.route("/checkout", methods=["POST"])
def submit_checkout():
    check_csrf()
    rows = cart_rows()
    if not rows:
        flash("Your cart is empty.", "danger")
        return redirect(url_for("view_cart"), code=303)

    total = sum((row["line_total"] for row in rows), Decimal("0.00"))
    values = {
        "name": request.form.get("name", ""),
        "email": request.form.get("email", ""),
        "address": request.form.get("address", ""),
    }
    try:
        form = CheckoutForm(**values)
    except ValidationError as error:
        return (
            render_template(
                "checkout.html",
                rows=rows,
                total=total,
                form=values,
                errors=[item["msg"] for item in error.errors()],
            ),
            422,
        )

    order = Order(
        customer_name=form.name,
        email=str(form.email),
        address=form.address,
        total=total,
    )
    for row in rows:
        product = row["product"]
        order.items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                quantity=row["quantity"],
                price_at_purchase=product.price,
            )
        )
    database = get_db()
    database.add(order)
    database.commit()
    database.refresh(order)
    session["cart"] = {}
    return redirect(url_for("order_confirmation", order_id=order.id), code=303)


@app.route("/orders/<int:order_id>/confirmation")
def order_confirmation(order_id):
    return render_template("confirmation.html", order=find_or_404(Order, order_id))


@app.route("/admin/login")
def admin_login_page():
    return render_template("admin/login.html")


@app.route("/admin/login", methods=["POST"])
def admin_login():
    check_csrf()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    admin = get_db().scalar(select(Admin).where(Admin.username == username))
    if admin and admin.check_password(password):
        session.clear()
        session["admin_id"] = admin.id
        session["admin_username"] = admin.username
        flash("Welcome to the admin area.", "success")
        return redirect(url_for("admin_dashboard"), code=303)
    flash("Invalid username or password.", "danger")
    return redirect(url_for("admin_login_page"), code=303)


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    check_csrf()
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("catalog"), code=303)


@app.route("/admin")
def admin_dashboard():
    login_redirect = require_admin()
    if login_redirect:
        return login_redirect
    products = get_db().scalars(select(Product).order_by(Product.name)).all()
    categories = get_db().scalars(select(Category).order_by(Category.name)).all()
    return render_template(
        "admin/dashboard.html",
        products=products,
        categories=categories,
    )


def product_form_page(product=None, values=None, errors=None):
    categories = get_db().scalars(select(Category).order_by(Category.name)).all()
    return (
        render_template(
            "admin/product_form.html",
            product=product,
            categories=categories,
            form=values or {},
            errors=errors or [],
        ),
        422 if errors else 200,
    )


def validate_product(values):
    try:
        return ProductForm(**values), []
    except ValidationError as error:
        return None, [item["msg"] for item in error.errors()]


def product_form_values():
    return {
        "name": request.form.get("name", ""),
        "description": request.form.get("description", ""),
        "price": request.form.get("price", ""),
        "image_url": request.form.get("image_url", ""),
        "category_id": request.form.get("category_id", ""),
        "is_active": request.form.get("is_active") == "on",
    }


def category_is_valid(category_id):
    return category_id.isdigit() and get_db().get(Category, int(category_id)) is not None


@app.route("/admin/products/new")
def admin_product_new_page():
    return require_admin() or product_form_page()


@app.route("/admin/products/new", methods=["POST"])
def admin_product_new():
    login_redirect = require_admin()
    if login_redirect:
        return login_redirect
    check_csrf()
    values = product_form_values()
    form, errors = validate_product(values)
    if not category_is_valid(values["category_id"]):
        errors.append("Choose an existing category.")
    if errors:
        return product_form_page(values=values, errors=errors)
    get_db().add(Product(**form.model_dump()))
    get_db().commit()
    flash("Product created.", "success")
    return redirect(url_for("admin_dashboard"), code=303)


@app.route("/admin/products/<int:product_id>/edit")
def admin_product_edit_page(product_id):
    return require_admin() or product_form_page(product=find_or_404(Product, product_id))


@app.route("/admin/products/<int:product_id>/edit", methods=["POST"])
def admin_product_edit(product_id):
    login_redirect = require_admin()
    if login_redirect:
        return login_redirect
    check_csrf()
    product = find_or_404(Product, product_id)
    values = product_form_values()
    form, errors = validate_product(values)
    if not category_is_valid(values["category_id"]):
        errors.append("Choose an existing category.")
    if errors:
        return product_form_page(product=product, values=values, errors=errors)
    for field, value in form.model_dump().items():
        setattr(product, field, value)
    get_db().commit()
    flash("Product updated.", "success")
    return redirect(url_for("admin_dashboard"), code=303)


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
def admin_product_delete(product_id):
    login_redirect = require_admin()
    if login_redirect:
        return login_redirect
    check_csrf()
    get_db().delete(find_or_404(Product, product_id))
    get_db().commit()
    flash("Product deleted.", "success")
    return redirect(url_for("admin_dashboard"), code=303)


@app.route("/admin/categories", methods=["POST"])
def admin_category_new():
    login_redirect = require_admin()
    if login_redirect:
        return login_redirect
    check_csrf()
    clean_name = request.form.get("name", "").strip()
    existing = get_db().scalar(select(Category).where(Category.name == clean_name))
    if not clean_name:
        flash("Category name is required.", "danger")
    elif existing:
        flash("That category already exists.", "danger")
    else:
        get_db().add(Category(name=clean_name))
        get_db().commit()
        flash("Category created.", "success")
    return redirect(url_for("admin_dashboard"), code=303)


@app.route("/admin/categories/<int:category_id>/rename", methods=["POST"])
def admin_category_rename(category_id):
    login_redirect = require_admin()
    if login_redirect:
        return login_redirect
    check_csrf()
    category = find_or_404(Category, category_id)
    clean_name = request.form.get("name", "").strip()
    duplicate = get_db().scalar(
        select(Category).where(Category.name == clean_name, Category.id != category.id)
    )
    if not clean_name or duplicate:
        flash("Enter a unique category name.", "danger")
    else:
        category.name = clean_name
        get_db().commit()
        flash("Category renamed.", "success")
    return redirect(url_for("admin_dashboard"), code=303)


@app.route("/admin/categories/<int:category_id>/delete", methods=["POST"])
def admin_category_delete(category_id):
    login_redirect = require_admin()
    if login_redirect:
        return login_redirect
    check_csrf()
    category = find_or_404(Category, category_id)
    if category.products:
        flash("Move or delete this category's products first.", "danger")
    else:
        get_db().delete(category)
        get_db().commit()
        flash("Category deleted.", "success")
    return redirect(url_for("admin_dashboard"), code=303)


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404
