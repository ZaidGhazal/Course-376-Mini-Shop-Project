import re

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import mini_shop.main as main_module
from mini_shop.database import Base
from mini_shop.models import Admin, Category, Order, Product


@pytest.fixture()
def database_factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with factory() as database:
        category = Category(name="Test")
        database.add(category)
        database.flush()
        database.add(
            Product(
                name="Test Product",
                description="Example",
                price="10.00",
                category=category,
            )
        )
        admin = Admin(username="admin")
        admin.set_password("test-password")
        database.add(admin)
        database.commit()
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(database_factory, monkeypatch):
    monkeypatch.setattr(main_module, "SessionLocal", database_factory)
    main_module.app.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    with main_module.app.test_client() as test_client:
        yield test_client


def csrf_from(response):
    html = response.get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_catalog_lists_products(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Test Product" in response.get_data(as_text=True)


def test_health_endpoint(client):
    assert client.get("/api/health").get_json() == {"status": "ok"}


def test_add_to_cart(client):
    csrf = csrf_from(client.get("/"))
    response = client.post(
        "/cart/items/1",
        data={"csrf_token": csrf},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Cart (1)" in response.get_data(as_text=True)


def test_admin_page_requires_login(client):
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_admin_can_log_in(client):
    csrf = csrf_from(client.get("/admin/login"))
    response = client.post(
        "/admin/login",
        data={
            "csrf_token": csrf,
            "username": "admin",
            "password": "test-password",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Inventory" in response.get_data(as_text=True)


def test_checkout_creates_order(client, database_factory):
    csrf = csrf_from(client.get("/"))
    client.post("/cart/items/1", data={"csrf_token": csrf})
    csrf = csrf_from(client.get("/checkout"))
    response = client.post(
        "/checkout",
        data={
            "csrf_token": csrf,
            "name": "Student Tester",
            "email": "student@example.edu",
            "address": "100 College Avenue",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Order received" in response.get_data(as_text=True)
    with database_factory() as database:
        order = database.scalar(select(Order))
        assert order is not None
        assert order.items[0].product_name == "Test Product"
