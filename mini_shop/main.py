"""FastAPI routes for server-rendered customer and admin pages."""

import os
import secrets
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from .database import Base, engine, get_db
from .models import Admin, Category, Order, OrderItem, Product
from .schemas import CheckoutForm, ProductForm


@asynccontextmanager
async def lifespan(application: FastAPI):
    os.makedirs("instance", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Mini Shop", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev-only-change-me"),
    max_age=30 * 60,
    same_site="lax",
    https_only=False,  # Change to True when deployed with HTTPS.
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def add_message(request: Request, text: str, category: str = "success"):
    request.session.setdefault("messages", []).append({"text": text, "category": category})


def csrf_token(request: Request):
    if "csrf_token" not in request.session:
        request.session["csrf_token"] = secrets.token_urlsafe(32)
    return request.session["csrf_token"]


def check_csrf(request: Request, submitted_token: str):
    saved_token = request.session.get("csrf_token", "")
    if not saved_token or not secrets.compare_digest(saved_token, submitted_token):
        raise HTTPException(status_code=400, detail="Invalid form security token")


def page_context(request: Request, **values):
    context = {
        "request": request,
        "csrf_token": csrf_token(request),
        "messages": request.session.pop("messages", []),
        "cart_count": sum(request.session.get("cart", {}).values()),
        "current_admin": request.session.get("admin_username"),
    }
    context.update(values)
    return context


def require_admin(request: Request):
    if "admin_id" not in request.session:
        add_message(request, "Please log in as an administrator.", "danger")
        return RedirectResponse("/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    return None


def find_or_404(database: Session, model, item_id: int):
    item = database.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def cart_rows(request: Request, database: Session):
    saved_cart = request.session.get("cart", {})
    product_ids = [int(product_id) for product_id in saved_cart]
    products = (
        database.scalars(select(Product).where(Product.id.in_(product_ids))).all()
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


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def catalog(request: Request, database: Session = Depends(get_db)):
    # TODO (Milestone 4): add search, category filtering, sorting, and pagination.
    products = database.scalars(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.name)
    ).all()
    return templates.TemplateResponse(
        request=request,
        name="catalog.html",
        context=page_context(request, products=products),
    )


@app.get("/products/{product_id}", response_class=HTMLResponse)
def product_detail(product_id: int, request: Request, database: Session = Depends(get_db)):
    product = find_or_404(database, Product, product_id)
    if not product.is_active:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request=request,
        name="product_detail.html",
        context=page_context(request, product=product),
    )


@app.post("/cart/items/{product_id}")
def add_to_cart(
    product_id: int,
    request: Request,
    csrf: Annotated[str, Form(alias="csrf_token")],
    database: Session = Depends(get_db),
):
    check_csrf(request, csrf)
    product = find_or_404(database, Product, product_id)
    if not product.is_active:
        raise HTTPException(status_code=404)
    cart = request.session.get("cart", {})
    key = str(product.id)
    cart[key] = int(cart.get(key, 0)) + 1
    request.session["cart"] = cart
    add_message(request, f"Added {product.name} to your cart.")
    return RedirectResponse(request.headers.get("referer", "/"), status_code=303)


@app.get("/cart", response_class=HTMLResponse)
def view_cart(request: Request, database: Session = Depends(get_db)):
    rows = cart_rows(request, database)
    total = sum((row["line_total"] for row in rows), Decimal("0.00"))
    return templates.TemplateResponse(
        request=request,
        name="cart.html",
        context=page_context(request, rows=rows, total=total),
    )


@app.post("/cart/items/{product_id}/remove")
def remove_from_cart(
    product_id: int,
    request: Request,
    csrf: Annotated[str, Form(alias="csrf_token")],
):
    check_csrf(request, csrf)
    cart = request.session.get("cart", {})
    cart.pop(str(product_id), None)
    request.session["cart"] = cart
    add_message(request, "Item removed from the cart.")
    return RedirectResponse("/cart", status_code=303)


@app.get("/checkout", response_class=HTMLResponse)
def checkout_page(request: Request, database: Session = Depends(get_db)):
    rows = cart_rows(request, database)
    if not rows:
        add_message(request, "Your cart is empty.", "danger")
        return RedirectResponse("/cart", status_code=303)
    total = sum((row["line_total"] for row in rows), Decimal("0.00"))
    return templates.TemplateResponse(
        request=request,
        name="checkout.html",
        context=page_context(request, rows=rows, total=total, form={}, errors=[]),
    )


@app.post("/checkout", response_class=HTMLResponse)
def submit_checkout(
    request: Request,
    csrf: Annotated[str, Form(alias="csrf_token")],
    name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    address: Annotated[str, Form()],
    database: Session = Depends(get_db),
):
    check_csrf(request, csrf)
    rows = cart_rows(request, database)
    if not rows:
        add_message(request, "Your cart is empty.", "danger")
        return RedirectResponse("/cart", status_code=303)
    total = sum((row["line_total"] for row in rows), Decimal("0.00"))
    values = {"name": name, "email": email, "address": address}
    try:
        form = CheckoutForm(**values)
    except ValidationError as error:
        return templates.TemplateResponse(
            request=request,
            name="checkout.html",
            context=page_context(
                request,
                rows=rows,
                total=total,
                form=values,
                errors=[item["msg"] for item in error.errors()],
            ),
            status_code=422,
        )

    order = Order(customer_name=form.name, email=str(form.email), address=form.address, total=total)
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
    database.add(order)
    database.commit()
    database.refresh(order)
    request.session["cart"] = {}
    return RedirectResponse(f"/orders/{order.id}/confirmation", status_code=303)


@app.get("/orders/{order_id}/confirmation", response_class=HTMLResponse)
def order_confirmation(order_id: int, request: Request, database: Session = Depends(get_db)):
    order = find_or_404(database, Order, order_id)
    return templates.TemplateResponse(
        request=request,
        name="confirmation.html",
        context=page_context(request, order=order),
    )


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="admin/login.html", context=page_context(request)
    )


@app.post("/admin/login")
def admin_login(
    request: Request,
    csrf: Annotated[str, Form(alias="csrf_token")],
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    database: Session = Depends(get_db),
):
    check_csrf(request, csrf)
    admin = database.scalar(select(Admin).where(Admin.username == username.strip()))
    if admin and admin.check_password(password):
        request.session.clear()
        request.session["admin_id"] = admin.id
        request.session["admin_username"] = admin.username
        add_message(request, "Welcome to the admin area.")
        return RedirectResponse("/admin", status_code=303)
    add_message(request, "Invalid username or password.", "danger")
    return RedirectResponse("/admin/login", status_code=303)


@app.post("/admin/logout")
def admin_logout(request: Request, csrf: Annotated[str, Form(alias="csrf_token")]):
    check_csrf(request, csrf)
    request.session.clear()
    add_message(request, "You have been logged out.")
    return RedirectResponse("/", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, database: Session = Depends(get_db)):
    redirect = require_admin(request)
    if redirect:
        return redirect
    products = database.scalars(select(Product).order_by(Product.name)).all()
    categories = database.scalars(select(Category).order_by(Category.name)).all()
    return templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context=page_context(request, products=products, categories=categories),
    )


def product_form_page(request, database, product=None, values=None, errors=None):
    categories = database.scalars(select(Category).order_by(Category.name)).all()
    return templates.TemplateResponse(
        request=request,
        name="admin/product_form.html",
        context=page_context(
            request,
            product=product,
            categories=categories,
            form=values or {},
            errors=errors or [],
        ),
        status_code=422 if errors else 200,
    )


def validate_product(name, description, price, image_url, category_id, is_active):
    values = {
        "name": name,
        "description": description,
        "price": price,
        "image_url": image_url,
        "category_id": category_id,
        "is_active": is_active,
    }
    try:
        return ProductForm(**values), values, []
    except ValidationError as error:
        return None, values, [item["msg"] for item in error.errors()]


def category_is_valid(database: Session, category_id: str):
    return category_id.isdigit() and database.get(Category, int(category_id)) is not None


@app.get("/admin/products/new", response_class=HTMLResponse)
def admin_product_new_page(request: Request, database: Session = Depends(get_db)):
    redirect = require_admin(request)
    return redirect or product_form_page(request, database)


@app.post("/admin/products/new")
def admin_product_new(
    request: Request,
    csrf: Annotated[str, Form(alias="csrf_token")],
    name: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    price: Annotated[str, Form()] = "",
    image_url: Annotated[str, Form()] = "",
    category_id: Annotated[str, Form()] = "",
    is_active: Annotated[bool, Form()] = False,
    database: Session = Depends(get_db),
):
    redirect = require_admin(request)
    if redirect:
        return redirect
    check_csrf(request, csrf)
    form, values, errors = validate_product(name, description, price, image_url, category_id, is_active)
    if not category_is_valid(database, category_id):
        errors.append("Choose an existing category.")
    if errors:
        return product_form_page(request, database, values=values, errors=errors)
    database.add(Product(**form.model_dump()))
    database.commit()
    add_message(request, "Product created.")
    return RedirectResponse("/admin", status_code=303)


@app.get("/admin/products/{product_id}/edit", response_class=HTMLResponse)
def admin_product_edit_page(product_id: int, request: Request, database: Session = Depends(get_db)):
    redirect = require_admin(request)
    if redirect:
        return redirect
    return product_form_page(request, database, product=find_or_404(database, Product, product_id))


@app.post("/admin/products/{product_id}/edit")
def admin_product_edit(
    product_id: int,
    request: Request,
    csrf: Annotated[str, Form(alias="csrf_token")],
    name: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    price: Annotated[str, Form()] = "",
    image_url: Annotated[str, Form()] = "",
    category_id: Annotated[str, Form()] = "",
    is_active: Annotated[bool, Form()] = False,
    database: Session = Depends(get_db),
):
    redirect = require_admin(request)
    if redirect:
        return redirect
    check_csrf(request, csrf)
    product = find_or_404(database, Product, product_id)
    form, values, errors = validate_product(name, description, price, image_url, category_id, is_active)
    if not category_is_valid(database, category_id):
        errors.append("Choose an existing category.")
    if errors:
        return product_form_page(request, database, product=product, values=values, errors=errors)
    for field, value in form.model_dump().items():
        setattr(product, field, value)
    database.commit()
    add_message(request, "Product updated.")
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/products/{product_id}/delete")
def admin_product_delete(
    product_id: int,
    request: Request,
    csrf: Annotated[str, Form(alias="csrf_token")],
    database: Session = Depends(get_db),
):
    redirect = require_admin(request)
    if redirect:
        return redirect
    check_csrf(request, csrf)
    database.delete(find_or_404(database, Product, product_id))
    database.commit()
    add_message(request, "Product deleted.")
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/categories")
def admin_category_new(
    request: Request,
    csrf: Annotated[str, Form(alias="csrf_token")],
    name: Annotated[str, Form()],
    database: Session = Depends(get_db),
):
    redirect = require_admin(request)
    if redirect:
        return redirect
    check_csrf(request, csrf)
    clean_name = name.strip()
    existing = database.scalar(select(Category).where(Category.name == clean_name))
    if not clean_name:
        add_message(request, "Category name is required.", "danger")
    elif existing:
        add_message(request, "That category already exists.", "danger")
    else:
        database.add(Category(name=clean_name))
        database.commit()
        add_message(request, "Category created.")
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/categories/{category_id}/rename")
def admin_category_rename(
    category_id: int,
    request: Request,
    csrf: Annotated[str, Form(alias="csrf_token")],
    name: Annotated[str, Form()],
    database: Session = Depends(get_db),
):
    redirect = require_admin(request)
    if redirect:
        return redirect
    check_csrf(request, csrf)
    category = find_or_404(database, Category, category_id)
    clean_name = name.strip()
    duplicate = database.scalar(
        select(Category).where(Category.name == clean_name, Category.id != category.id)
    )
    if not clean_name or duplicate:
        add_message(request, "Enter a unique category name.", "danger")
    else:
        category.name = clean_name
        database.commit()
        add_message(request, "Category renamed.")
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/categories/{category_id}/delete")
def admin_category_delete(
    category_id: int,
    request: Request,
    csrf: Annotated[str, Form(alias="csrf_token")],
    database: Session = Depends(get_db),
):
    redirect = require_admin(request)
    if redirect:
        return redirect
    check_csrf(request, csrf)
    category = find_or_404(database, Category, category_id)
    if category.products:
        add_message(request, "Move or delete this category's products first.", "danger")
    else:
        database.delete(category)
        database.commit()
        add_message(request, "Category deleted.")
    return RedirectResponse("/admin", status_code=303)


@app.exception_handler(404)
def not_found(request: Request, error):
    return templates.TemplateResponse(
        request=request,
        name="404.html",
        context=page_context(request),
        status_code=404,
    )

