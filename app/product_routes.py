import logging
from time import perf_counter

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models import Product
from app.stock_routes import DailyProductStock, today_ist

router = APIRouter(prefix="/products", tags=["Products"])
logger = logging.getLogger("fishspot.products")


@router.get("/")
def get_products(session: Session = Depends(get_session)):
    request_started = perf_counter()

    step_started = perf_counter()
    products = session.exec(
        select(Product).order_by(Product.category, Product.name, Product.id)
    ).all()
    products_query_seconds = perf_counter() - step_started

    if not products:
        logger.info(
            "products_timing products_query=%.3fs total=%.3fs count=0",
            products_query_seconds,
            perf_counter() - request_started,
        )
        return []

    product_ids = [product.id for product in products]
    stock_date = today_ist()

    step_started = perf_counter()
    stock_rows = session.exec(
        select(DailyProductStock).where(
            DailyProductStock.product_id.in_(product_ids),
            DailyProductStock.stock_date == stock_date,
        )
    ).all()
    stock_query_seconds = perf_counter() - step_started
    stock_by_product = {row.product_id: row for row in stock_rows}

    missing_rows = [
        DailyProductStock(
            product_id=product_id,
            stock_date=stock_date,
            total_grams=10000,
            sold_grams=0,
        )
        for product_id in product_ids
        if product_id not in stock_by_product
    ]

    insert_seconds = 0.0
    if missing_rows:
        step_started = perf_counter()
        session.add_all(missing_rows)
        session.commit()
        insert_seconds = perf_counter() - step_started
        for row in missing_rows:
            stock_by_product[row.product_id] = row

    step_started = perf_counter()
    result = []
    for product in products:
        stock = stock_by_product.get(product.id)
        if stock is None:
            # Defensive fallback: do not fail the entire catalogue response.
            remaining = 10000
            total_grams = 10000
        else:
            total_grams = stock.total_grams
            remaining = max(0, total_grams - stock.sold_grams)

        item = product.model_dump()
        item["stock_remaining_grams"] = remaining
        item["stock_total_grams"] = total_grams
        item["stock_date"] = stock_date.isoformat()
        item["is_out_of_stock"] = remaining <= 0
        result.append(item)
    serialize_seconds = perf_counter() - step_started

    logger.info(
        "products_timing count=%d stock_rows=%d missing_stock_rows=%d "
        "products_query=%.3fs stock_query=%.3fs stock_insert=%.3fs "
        "serialize=%.3fs total=%.3fs",
        len(products),
        len(stock_rows),
        len(missing_rows),
        products_query_seconds,
        stock_query_seconds,
        insert_seconds,
        serialize_seconds,
        perf_counter() - request_started,
    )

    return result
