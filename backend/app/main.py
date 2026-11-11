"""ProfitLens REST API. Demo workspace is read-only; real data is tenant-isolated."""
from __future__ import annotations
import csv, io, os, re
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from .core import (Base, engine, get_db, SessionLocal, User, Workspace, Product, Order, Return, Alert,
                   hash_password, verify_password, make_token, parse_token, authorized_workspace, current_user)
from .analytics import overview, detect_alerts, scoped_data, money
from .seed import seed_demo

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    if os.getenv('SEED_DEMO','true').lower() == 'true':
        with SessionLocal() as db:seed_demo(db)
    yield

app=FastAPI(title='ProfitLens API',version='1.0.0',lifespan=lifespan)
origins = [x.strip() for x in os.getenv('CORS_ORIGINS','http://localhost:3000').split(',') if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=['GET','POST','PATCH'],allow_headers=['Authorization','Content-Type'])

class Credentials(BaseModel):
    email: str
    password: str
class Registration(Credentials):
    name: str = Field(min_length=2,max_length=100)
class ChatRequest(BaseModel):
    question: str = Field(min_length=2,max_length=500)

def optional_user(authorization: str | None = Header(None),db:Session=Depends(get_db)) -> User|None:
    if not authorization:return None
    if not authorization.startswith('Bearer '):raise HTTPException(401,'Invalid authorization header')
    user=db.get(User,parse_token(authorization[7:]))
    if not user:raise HTTPException(401,'Account unavailable')
    return user

def scope(wid:int,db:Session,user:User|None):return authorized_workspace(db,user,wid)
def write_scope(wid:int,db:Session,user:User):
    ws=scope(wid,db,user)
    if ws.is_demo:raise HTTPException(403,'Demo workspace is read-only. Switch to My Workspace to import.')
    return ws

@app.get('/health')
def health():return {'status':'ok'}
@app.post('/auth/register',status_code=201)
def register(payload:Registration,db:Session=Depends(get_db)):
    email=payload.email.strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise HTTPException(422,'Invalid email address')
    if len(payload.password)<8:raise HTTPException(422,'Password requires at least 8 characters')
    if db.scalar(select(User).where(User.email==email)):raise HTTPException(409,'Email already registered')
    user=User(email=email,name=payload.name.strip(),password_hash=hash_password(payload.password));db.add(user);db.flush()
    ws=Workspace(name=f'{user.name}’s Workspace',owner_id=user.id);db.add(ws);db.commit()
    return {'token':make_token(user.id),'user':{'id':user.id,'name':user.name,'email':user.email}}
@app.post('/auth/login')
def login(payload:Credentials,db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==payload.email.strip().lower()))
    if not user or not verify_password(payload.password,user.password_hash):raise HTTPException(401,'Invalid email or password')
    return {'token':make_token(user.id),'user':{'id':user.id,'name':user.name,'email':user.email}}
@app.get('/auth/me')
def me(user:User=Depends(current_user)):return {'id':user.id,'name':user.name,'email':user.email}
@app.get('/workspaces')
def workspaces(db:Session=Depends(get_db),user:User|None=Depends(optional_user)):
    stmt=select(Workspace).where(Workspace.is_demo==True)
    demo=db.scalars(stmt).all()
    personal=db.scalars(select(Workspace).where(Workspace.owner_id==user.id)).all() if user else []
    return [{'id':w.id,'name':w.name,'is_demo':w.is_demo} for w in demo+personal]
@app.get('/workspaces/{wid}/overview')
def summary(wid:int,days:int=Query(90,ge=7,le=365),db:Session=Depends(get_db),user:User|None=Depends(optional_user)):
    scope(wid,db,user);return overview(db,wid,days)
@app.get('/workspaces/{wid}/orders')
def orders(wid:int,limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0),
           db:Session=Depends(get_db),user:User|None=Depends(optional_user)):
    scope(wid,db,user)
    stmt=select(Order).where(Order.workspace_id==wid).order_by(Order.purchased_at.desc())
    count=db.scalar(select(func.count(Order.id)).where(Order.workspace_id==wid)) or 0
    rows=db.scalars(stmt.offset(offset).limit(limit)).all();product_ids={o.product_id for o in rows}
    products={p.id:p for p in db.scalars(select(Product).where(Product.id.in_(product_ids))).all()}
    returns={r.order_id:r for r in db.scalars(select(Return).where(Return.workspace_id==wid,Return.order_id.in_([o.id for o in rows]))).all()} if rows else {}
    return {'total':count,'items':[{'id':o.external_id,'date':o.purchased_at.isoformat(),
           'product':products[o.product_id].name,'sku':products[o.product_id].sku,
           'qty':o.quantity,'revenue':money(o.quantity*o.unit_price),'status':'returned' if o.id in returns else o.status,
           'profit':money(o.quantity*(o.unit_price-o.unit_cost)-o.shipping-o.platform_fee-(returns[o.id].refunded_amount+returns[o.id].return_shipping if o.id in returns else 0))} for o in rows]}
@app.get('/workspaces/{wid}/inventory')
def inventory(wid:int,db:Session=Depends(get_db),user:User|None=Depends(optional_user)):
    scope(wid,db,user)
    return [{'sku':p.sku,'name':p.name,'category':p.category,'cost':p.cost,'price':p.price,'stock':p.stock,'low_stock':p.stock<20} for p in db.scalars(select(Product).where(Product.workspace_id==wid).order_by(Product.name)).all()]
@app.get('/workspaces/{wid}/returns')
def returns(wid:int,limit:int=Query(100,ge=1,le=200),db:Session=Depends(get_db),user:User|None=Depends(optional_user)):
    scope(wid,db,user)
    rows=db.scalars(select(Return).where(Return.workspace_id==wid).order_by(Return.created_at.desc()).limit(limit)).all()
    orders={o.id:o for o in db.scalars(select(Order).where(Order.id.in_([r.order_id for r in rows]))).all()}
    products={p.id:p for p in db.scalars(select(Product).where(Product.id.in_([o.product_id for o in orders.values()]))).all()}
    return [{'id':r.external_id,'order':orders[r.order_id].external_id,'product':products[orders[r.order_id].product_id].name,'reason':r.reason,'refund':r.refunded_amount,'date':r.created_at.isoformat(),'restockable':r.restockable} for r in rows]
@app.get('/workspaces/{wid}/alerts')
def alerts(wid:int,db:Session=Depends(get_db),user:User|None=Depends(optional_user)):
    scope(wid,db,user)
    return [{'id':a.id,'title':a.title,'description':a.description,'kind':a.kind,'severity':a.severity,'acknowledged':a.acknowledged,'date':a.created_at.isoformat()} for a in db.scalars(select(Alert).where(Alert.workspace_id==wid).order_by(Alert.created_at.desc())).all()]
@app.post('/workspaces/{wid}/alerts/scan')
def scan(wid:int,db:Session=Depends(get_db),user:User|None=Depends(optional_user)):
    ws=scope(wid,db,user)
    new=detect_alerts(db,wid,notify=not ws.is_demo)
    return {'created':len(new)}
@app.patch('/workspaces/{wid}/alerts/{alert_id}/acknowledge')
def acknowledge(wid:int,alert_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    write_scope(wid,db,user)
    a=db.scalar(select(Alert).where(Alert.id==alert_id,Alert.workspace_id==wid))
    if not a:raise HTTPException(404,'Alert not found')
    a.acknowledged=True;db.commit();return {'ok':True}

REQUIRED = {
 'products':['sku','name','category','cost','price','stock'],
 'orders':['external_id','sku','purchased_at','quantity','unit_price','unit_cost','shipping','platform_fee','status'],
 'returns':['external_id','order_external_id','reason','refunded_amount','return_shipping','restockable']}

def parse_date(value:str) -> datetime:
    try:return datetime.fromisoformat(value.replace('Z','+00:00')).replace(tzinfo=None)
    except ValueError:raise ValueError('Date must use ISO 8601 format')
def number(row:dict,key:str,min_value:float=0) -> float:
    val=float(row[key]);
    if not (min_value<=val<1e12):raise ValueError(f'{key} is outside the allowed range')
    return val

def ingest_rows(db:Session,wid:int,kind:str,rows:list[dict]) -> int:
    if kind not in REQUIRED:raise ValueError('Unknown import type')
    if not rows:return 0
    missing=set(REQUIRED[kind])-set(rows[0])
    if missing:raise ValueError('Missing columns: '+', '.join(sorted(missing)))
    count=0
    seen=set()
    for line,row in enumerate(rows,start=2):
        try:
            if kind=='products':
                sku=row['sku'].strip()
                if not sku:raise ValueError('SKU is required')
                if sku in seen:continue
                seen.add(sku)
                if db.scalar(select(Product.id).where(Product.workspace_id==wid,Product.sku==sku)):continue
                p=Product(workspace_id=wid,sku=sku,name=row['name'].strip()[:180],category=row['category'].strip()[:80],
                          cost=number(row,'cost'),price=number(row,'price'),stock=int(number(row,'stock')))
                if not p.name:raise ValueError('Name is required')
                db.add(p)
            elif kind=='orders':
                external=row['external_id'].strip()
                if not external:raise ValueError('Order ID is required')
                if external in seen:continue
                seen.add(external)
                if db.scalar(select(Order.id).where(Order.workspace_id==wid,Order.external_id==external)):continue
                p=db.scalar(select(Product).where(Product.workspace_id==wid,Product.sku==row['sku'].strip()))
                if not p:raise ValueError('Product SKU not found; import products first')
                qty=int(number(row,'quantity',1));status=row['status'].strip().lower()
                if status not in {'delivered','processing','shipped','cancelled'}:raise ValueError('Unsupported order status')
                db.add(Order(workspace_id=wid,external_id=external,product_id=p.id,purchased_at=parse_date(row['purchased_at']),
                    quantity=qty,unit_price=number(row,'unit_price'),unit_cost=number(row,'unit_cost'),
                    shipping=number(row,'shipping'),platform_fee=number(row,'platform_fee'),status=status))
            else:
                external=row['external_id'].strip();order_id=row['order_external_id'].strip()
                if not external:raise ValueError('Return ID is required')
                if external in seen:continue
                seen.add(external)
                if db.scalar(select(Return.id).where(Return.workspace_id==wid,Return.external_id==external)):continue
                o=db.scalar(select(Order).where(Order.workspace_id==wid,Order.external_id==order_id))
                if not o:raise ValueError('Order not found; import orders first')
                if db.scalar(select(Return.id).where(Return.order_id==o.id)):raise ValueError('Order already returned')
                refund=number(row,'refunded_amount')
                if refund > o.quantity*o.unit_price:raise ValueError('Refund exceeds order gross revenue')
                boolval=row['restockable'].strip().lower()
                if boolval not in ('true','false','1','0','yes','no'):raise ValueError('Invalid restockable flag')
                db.add(Return(workspace_id=wid,external_id=external,order_id=o.id,reason=row['reason'].strip()[:100],
                    refunded_amount=refund,return_shipping=number(row,'return_shipping'),restockable=boolval in ('true','1','yes')))
            db.flush();count+=1
        except (ValueError,KeyError,OverflowError) as e:
            db.rollback();raise ValueError(f'CSV row {line}: {e}')
    db.commit();return count

@app.post('/workspaces/{wid}/import/{kind}')
async def import_csv(wid:int,kind:str,file:UploadFile=File(...),db:Session=Depends(get_db),user:User=Depends(current_user)):
    write_scope(wid,db,user)
    if kind not in REQUIRED:raise HTTPException(404,'Unknown dataset type')
    if not file.filename or not file.filename.lower().endswith('.csv'):raise HTTPException(422,'Upload a .csv file')
    contents=await file.read(2_000_001)
    if len(contents)>2_000_000:raise HTTPException(413,'File is too large (limit 2 MB)')
    try:
        reader=csv.DictReader(io.StringIO(contents.decode('utf-8-sig')))
        rows=list(reader)
        if len(rows)>10000:raise ValueError('Maximum 10,000 rows per upload')
        count=ingest_rows(db,wid,kind,rows)
    except (UnicodeDecodeError,csv.Error,ValueError) as e:raise HTTPException(422,str(e))
    return {'imported':count,'skipped':len(rows)-count,'type':kind}

@app.post('/workspaces/{wid}/assistant')
async def assistant(wid:int,payload:ChatRequest,db:Session=Depends(get_db),user:User|None=Depends(optional_user)):
    scope(wid,db,user)
    report=overview(db,wid,90);k=report['kpis'];q=payload.question.lower()
    # Deterministic, factual fallback works even without API credits.
    if any(w in q for w in ['return','refund']):
        answer=f'The return rate is {k["return_rate"]}% across {k["returns"]:,} returns. Total refunds are ₹{k["refunds"]:,.0f} in the last 90 days.'
    elif any(w in q for w in ['profit','margin','loss']):
        losses=[p['name'] for p in report['products'] if p['profit']<0]
        answer=f'Net profit is ₹{k["profit"]:,.0f} with a {k["margin"]}% margin over the last 90 days.' + (f' Products with negative profit: {", ".join(losses[:4])}.' if losses else ' No products have negative cumulative profit in this period.')
    elif any(w in q for w in ['product','best','top']):
        top=report['products'][:3]
        answer='Top products by revenue: '+', '.join(f'{p["name"]} (₹{p["revenue"]:,.0f})' for p in top)+'.' if top else 'No product data yet.'
    else:
        answer=f'Over the last 90 days: {k["orders"]:,} orders, ₹{k["net_revenue"]:,.0f} net revenue, ₹{k["profit"]:,.0f} profit, {k["margin"]}% margin, and {k["return_rate"]}% return rate. Ask about returns, profits, or products for details.'
    api_key=os.getenv('OPENAI_API_KEY','')
    if api_key:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=18) as client:
                res=await client.post('https://api.openai.com/v1/chat/completions',headers={'Authorization':f'Bearer {api_key}'},json={
                    'model':os.getenv('OPENAI_MODEL','gpt-4.1-mini'),
                    'messages':[{'role':'system','content':'You are a careful commerce analyst. Answer using ONLY the following aggregate JSON snapshot. Clearly explain that the period is last 90 days. Never fabricate facts. Be concise. Snapshot: '+__import__('json').dumps({'kpis':k,'top_products':report['products'][:10],'return_reasons':report['reasons']})},
                                {'role':'user','content':payload.question}], 'max_tokens':300})
                res.raise_for_status();answer=res.json()['choices'][0]['message']['content']
        except (httpx.HTTPError,KeyError,IndexError,TypeError,ValueError):pass
    return {'answer':answer,'period_days':90,'ai_enabled':bool(api_key)}
