from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.database import get_session
from app.models import Product

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("/")
def get_products(session: Session = Depends(get_session)):
    statement = (
        select(Product)
        .where(Product.is_active == True)  # noqa: E712
        .order_by(Product.category, Product.name, Product.id)
    )
    return session.exec(statement).all()
