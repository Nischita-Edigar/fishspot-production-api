from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.database import get_session
from app.models import Product
from app.stock_routes import DailyProductStock, today_ist
from app.product_cache import get_cached_products, set_cached_products

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("/")
def get_products(session: Session = Depends(get_session)):
    """Return the catalogue with current daily stock; cache avoids repeated DB round trips."""
    cached = get_cached_products()
    if cached is not None:
        return cached

    products = session.exec(
        select(Product).order_by(Product.category, Product.name, Product.id)
    ).all()
    if not products:
        set_cached_products([])
        return []

    product_ids = [product.id for product in products]
    stock_date = today_ist()
    stock_rows = session.exec(
        select(DailyProductStock).where(
            DailyProductStock.product_id.in_(product_ids),
            DailyProductStock.stock_date == stock_date,
        )
    ).all()
    stock_by_product = {row.product_id: row for row in stock_rows}

    result = []
    for product in products:
        stock = stock_by_product.get(product.id)
        # Products without a row have the standard 10 kg daily starting stock.
        total_grams = stock.total_grams if stock else 10000
        sold_grams = stock.sold_grams if stock else 0
        remaining = max(0, total_grams - sold_grams)
        item = product.model_dump()
        item["stock_remaining_grams"] = remaining
        item["stock_total_grams"] = total_grams
        item["stock_date"] = stock_date.isoformat()
        item["is_out_of_stock"] = remaining <= 0
        result.append(item)

    set_cached_products(result)
    return result
