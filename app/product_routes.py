from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.database import get_session
from app.models import Product
from app.stock_routes import stock_row, today_ist

router = APIRouter(prefix="/products", tags=["Products"])

@router.get("/")
def get_products(session: Session = Depends(get_session)):
    products=session.exec(select(Product).order_by(Product.category, Product.name, Product.id)).all()
    result=[]
    for product in products:
        stock=stock_row(session,product.id)
        remaining=max(0,stock.total_grams-stock.sold_grams)
        item=product.model_dump()
        item["stock_remaining_grams"]=remaining
        item["stock_total_grams"]=stock.total_grams
        item["stock_date"]=today_ist().isoformat()
        item["is_out_of_stock"]=remaining<=0
        result.append(item)
    return result
