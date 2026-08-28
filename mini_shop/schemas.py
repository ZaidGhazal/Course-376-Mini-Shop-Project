"""Pydantic models keep form validation in Python."""

from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field


class CheckoutForm(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    address: str = Field(min_length=10, max_length=500)


class ProductForm(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    price: Decimal = Field(ge=0, decimal_places=2)
    image_url: str = Field(default="", max_length=500)
    category_id: int = Field(gt=0)
    is_active: bool = True

