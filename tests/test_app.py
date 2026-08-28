import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from mini_shop.database import Base, get_db
from mini_shop.main import app
from mini_shop.models import Admin, Category, Order, Product


@pytest.fixture()
def database_factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with factory() as database:
        category = Category(name="Test")
        database.add(category)
        database.flush()
        database.add(Product(name="Test Product", description="Example", price="10.00", category=category))
        admin = Admin(username="admin")
        admin.set_password("test-password")
        database.add(admin)
        database.commit()
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(database_factory):
    def override_database():
        with database_factory() as database:
            yield database

    app.dependency_overrides[get_db] = override_database
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def csrf_from(response):
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match is not None
    return match.group(1)


def test_catalog_lists_products(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Test Product" in response.text


def test_health_endpoint(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_add_to_cart(client):
    csrf = csrf_from(client.get("/"))
    response = client.post("/cart/items/1", data={"csrf_token": csrf}, follow_redirects=True)
    assert response.status_code == 200
    assert "Cart (1)" in response.text


def test_admin_page_requires_login(client):
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_admin_can_log_in(client):
    csrf = csrf_from(client.get("/admin/login"))
    response = client.post(
        "/admin/login",
        data={"csrf_token": csrf, "username": "admin", "password": "test-password"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Inventory" in response.text


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
    assert "Order received" in response.text
    with database_factory() as database:
        order = database.scalar(select(Order))
        assert order is not None
        assert order.items[0].product_name == "Test Product"

