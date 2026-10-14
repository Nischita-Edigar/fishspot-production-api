from datetime import date, datetime, timezone
import re
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as DBField, Session, select
from sqlalchemy import update
from app.database import get_session
from app.models import Product
from app.admin_routes import require_admin

router = APIRouter(tags=["Daily Stock"])
IST = ZoneInfo("Asia/Kolkata")
def today_ist(): return datetime.now(IST).date()

class DailyProductStock(SQLModel, table=True):
    __tablename__ = "daily_product_stock"
    id: int | None = DBField(default=None, primary_key=True)
    product_id: int = DBField(index=True)
    stock_date: date = DBField(index=True)
    total_grams: int = 10000
    sold_grams: int = 0

class StockUpdate(BaseModel):
    total_kg: float = Field(ge=0, le=10000)

class RestockUpdate(BaseModel):
    add_kg: float = Field(gt=0, le=10000)

def stock_row(session: Session, product_id: int):
    day=today_ist()
    row=session.exec(select(DailyProductStock).where(DailyProductStock.product_id==product_id, DailyProductStock.stock_date==day)).first()
    if row is None:
        row=DailyProductStock(product_id=product_id, stock_date=day, total_grams=10000, sold_grams=0)
        session.add(row); session.commit(); session.refresh(row)
    return row

@router.get("/admin/stock", dependencies=[Depends(require_admin)])
def list_stock(session: Session=Depends(get_session)):
    rows=session.exec(select(Product).order_by(Product.category, Product.name)).all()
    result=[]
    for p in rows:
        s=stock_row(session,p.id)
        result.append({"product_id":p.id,"name":p.name,"category":p.category,"total_kg":s.total_grams/1000,"sold_kg":s.sold_grams/1000,"remaining_kg":max(0,s.total_grams-s.sold_grams)/1000})
    return {"date":today_ist().isoformat(),"products":result}

@router.patch("/admin/stock/{product_id}", dependencies=[Depends(require_admin)])
def update_stock(product_id:int, data:StockUpdate, session:Session=Depends(get_session)):
    if not session.get(Product,product_id): raise HTTPException(404,"Product not found")
    s=stock_row(session,product_id); s.total_grams=round(data.total_kg*1000)
    if s.total_grams < s.sold_grams: raise HTTPException(400,"Total stock cannot be less than stock already sold")
    session.add(s); session.commit(); session.refresh(s)
    return {"product_id":product_id,"total_kg":s.total_grams/1000,"sold_kg":s.sold_grams/1000,"remaining_kg":(s.total_grams-s.sold_grams)/1000}

def consume_stock(session:Session, items:list[dict]):
    """Atomically consume captured-order stock. Item quantity is 250g per unit by default."""
    for item in items:
        pid=int(item["product_id"]); qty=int(item["quantity"]); p=session.get(Product,pid)
        if not p: raise ValueError("Product no longer exists")
        match=re.match(r"\s*(\d+(?:\.\d+)?)\s*(kg|g)\s*$",p.net_quantity or "250g",re.I)
        grams=round(float(match.group(1))*(1000 if match and match.group(2).lower()=="kg" else 1)) if match else 250
        s=stock_row(session,pid); required=grams*qty
        result=session.exec(update(DailyProductStock).where(DailyProductStock.id==s.id, DailyProductStock.total_grams-DailyProductStock.sold_grams>=required).values(sold_grams=DailyProductStock.sold_grams+required))
        if result.rowcount != 1: raise ValueError(f"Not enough stock for {p.name}")
    session.commit()


@router.post("/admin/stock/{product_id}/restock", dependencies=[Depends(require_admin)])
def add_restock(product_id: int, data: RestockUpdate, session: Session = Depends(get_session)):
    """Add new stock to today's total without resetting quantity already sold."""
    if not session.get(Product, product_id):
        raise HTTPException(404, "Product not found")
    s = stock_row(session, product_id)
    s.total_grams += round(data.add_kg * 1000)
    session.add(s)
    session.commit()
    session.refresh(s)
    return {
        "product_id": product_id,
        "total_kg": s.total_grams / 1000,
        "sold_kg": s.sold_grams / 1000,
        "remaining_kg": max(0, s.total_grams - s.sold_grams) / 1000,
        "added_kg": round(data.add_kg, 3),
    }
