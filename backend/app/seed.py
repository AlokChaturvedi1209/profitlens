"""Deterministic demo data with realistic product economics and returns."""
import random
from datetime import datetime,timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from .core import Workspace, Product, Order, Return, SessionLocal, Base, engine

CATALOG = [
 ('EL-101','Wireless Noise-Cancelling Headphones','Electronics',1899,3999,175),
 ('EL-102','Compact Bluetooth Speaker','Electronics',750,1999,120),
 ('EL-103','65W Fast Charging Adapter','Electronics',460,1199,230),
 ('FA-201','Everyday Canvas Sneakers','Fashion',899,2499,110),
 ('FA-202','Relaxed Cotton Overshirt','Fashion',550,1599,210),
 ('FA-203','Minimal Leather Wallet','Fashion',340,1099,150),
 ('HO-301','Ceramic Coffee Mug Set','Home & Living',480,1399,95),
 ('HO-302','Aroma Diffuser','Home & Living',1200,2499,75),
 ('HO-303','Bamboo Desk Organizer','Home & Living',380,999,180),
 ('BE-401','Daily Hydration Serum','Beauty',320,1099,140),
 ('BE-402','Sunscreen SPF 50','Beauty',270,899,190),
 ('SP-501','Insulated Gym Bottle','Sports',490,1499,105),
 ('SP-502','Resistance Band Kit','Sports',300,1299,160),
 ('FA-204','Premium Travel Backpack','Fashion',1900,2599,65),
]
REASONS = ['Size or fit issue','Damaged in transit','Item not as described','Changed mind','Quality concerns']

def seed_demo(db: Session) -> int:
    existing = db.scalar(select(Workspace).where(Workspace.is_demo == True))
    if existing: return existing.id
    ws=Workspace(name='Northstar Commerce · Demo',is_demo=True)
    db.add(ws);db.flush()
    products=[]
    for sku,name,cat,cost,price,stock in CATALOG:
        p=Product(workspace_id=ws.id,sku=sku,name=name,category=cat,cost=cost,price=price,stock=stock)
        db.add(p);products.append(p)
    db.flush();rng=random.Random(424242);now=datetime.utcnow()
    for i in range(3200):
        age = rng.randrange(0,120)
        p=rng.choices(products,weights=[12,8,11,9,10,7,8,6,10,9,12,7,9,5],k=1)[0]
        qty=rng.choices([1,2,3],[80,16,4])[0]
        # Deliberate revenue dip in the past few completed days
        if 1 <= age <= 3 and rng.random() < .65: continue
        discount = rng.choice([1,1,.95,.9])
        o=Order(workspace_id=ws.id,external_id=f'NS-{100000+i}',product_id=p.id,
                purchased_at=now-timedelta(days=age,hours=rng.randrange(24),minutes=rng.randrange(60)),
                quantity=qty,unit_price=round(p.price*discount,2),unit_cost=p.cost,
                shipping=rng.choice([55,70,90,120]),platform_fee=round(p.price*qty*.065,2),status='delivered')
        db.add(o);db.flush()
        rate = .31 if p.sku=='FA-204' else (.24 if p.sku=='HO-302' else .055)
        if rng.random()<rate:
            db.add(Return(workspace_id=ws.id,external_id=f'RT-{100000+i}',order_id=o.id,
                reason=rng.choice(REASONS),refunded_amount=round(o.unit_price*qty,2),
                return_shipping=rng.choice([55,80,110]),restockable=rng.random()<.7))
    db.commit();return ws.id

def initialize() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:seed_demo(db)
if __name__=='__main__':initialize()
