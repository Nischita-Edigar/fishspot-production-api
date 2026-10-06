from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Product(SQLModel, table=True):
    __tablename__ = "products"

    id: int | None = Field(default=None, primary_key=True)

    # Basic product information
    name: str = Field(index=True)
    category: str = Field(index=True)

    # Product details
    size: str | None = None
    fish_size: str | None = None
    cut: str | None = None
    pieces: str | None = None

    # Pricing
    price: float = 0.0

    # Product image
    image: str | None = None

    # Product availability
    is_active: bool = True

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )