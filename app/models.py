from datetime import datetime, timezone
from sqlmodel import Field, SQLModel


class Product(SQLModel, table=True):
    __tablename__ = "products"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    category: str = Field(index=True)
    size: str | None = None
    fish_size: str | None = None
    cut: str | None = None
    pieces: str | None = None
    price: float = 0.0
    image: str | None = None
    is_active: bool = True

    # Product detail page fields
    net_quantity: str = Field(default="250g")
    protein_per_100g: float | None = Field(default=None)
    calories_per_100g: float | None = Field(default=None)
    healthy_fat_per_100g: float | None = Field(default=None)
    description: str | None = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
