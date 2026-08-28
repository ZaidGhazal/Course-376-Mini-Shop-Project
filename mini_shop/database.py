"""Database configuration shared by the application and seed script."""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./instance/mini_shop.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()

