"""Create a small set of demonstration data for the student starter."""

import os

from sqlalchemy import select

from mini_shop.database import Base, SessionLocal, engine
from mini_shop.models import Admin, Category, Product


def seed():
    os.makedirs("instance", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as database:
        categories = {}
        for name in ("Books", "Home", "Technology"):
            category = database.scalar(select(Category).where(Category.name == name))
            if category is None:
                category = Category(name=name)
                database.add(category)
            categories[name] = category
        database.flush()

        if database.scalar(select(Product).limit(1)) is None:
            database.add_all(
                [
                    Product(name="Python Pocket Guide", description="A compact reference for Python fundamentals.", price="18.99", category=categories["Books"]),
                    Product(name="Desk Plant", description="A low-maintenance plant for a study space.", price="12.50", category=categories["Home"]),
                    Product(name="USB-C Study Lamp", description="An adjustable lamp with three brightness levels.", price="27.00", category=categories["Technology"]),
                ]
            )

        admin = database.scalar(select(Admin).where(Admin.username == "admin"))
        if admin is None:
            admin = Admin(username="admin")
            admin.set_password("changeme")
            database.add(admin)
        database.commit()

    print("Sample data created.")
    print("Development admin: admin / changeme")
    print("Change this password before using the app outside local development.")


if __name__ == "__main__":
    seed()
