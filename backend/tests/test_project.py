import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
os.environ['SEED_DEMO']='false'
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine, select
import app.core as core
import app.main as main
from app.analytics import order_financials, detect_alerts
from app.seed import seed_demo
from app.core import Base, SessionLocal, Workspace, Product, Order, Return, Alert, make_token, parse_token, hash_password, verify_password
from datetime import datetime,timedelta
import pytest

@pytest.fixture
def db():
    engine=create_engine('sqlite:///:memory:',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import Session
    with Session(engine,expire_on_commit=False) as s:yield s
    Base.metadata.drop_all(engine)

@pytest.fixture
def client(db):
    def override():yield db
    main.app.dependency_overrides[core.get_db]=override
    with TestClient(main.app) as c:yield c
    main.app.dependency_overrides.clear()

def test_auth_hash():
    x=hash_password('example-password');assert verify_password('example-password',x)
    assert not verify_password('wrong',x)
def test_session_tokens():
    assert parse_token(make_token(21))==21
    from fastapi import HTTPException
    with pytest.raises(HTTPException):parse_token('1.1234.deadbeef')
def test_financial_math():
    from types import SimpleNamespace
    o=SimpleNamespace(quantity=2,unit_price=500,unit_cost=200,shipping=45,platform_fee=55)
    r=SimpleNamespace(refunded_amount=500,return_shipping=70)
    assert order_financials(o)['profit']==500
    assert order_financials(o,r)['profit']==-70

def register(client,email='a@example.com'):
    r=client.post('/auth/register',json={'name':'Alice','email':email,'password':'password123'})
    assert r.status_code==201,r.text
    return r.json()['token']
def test_health(client):assert client.get('/health').json()=={'status':'ok'}
def test_register_login_and_isolation(client,db):
    a=register(client);b=register(client,'b@example.com')
    w=client.get('/workspaces',headers={'Authorization':f'Bearer {a}'}).json()[0]['id']
    assert client.get(f'/workspaces/{w}/overview',headers={'Authorization':f'Bearer {b}'}).status_code==404
    assert client.get(f'/workspaces/{w}/overview',headers={'Authorization':f'Bearer {a}'}).status_code==200
    assert client.post('/auth/login',json={'email':'a@example.com','password':'wrong'}).status_code==401
    assert client.post('/auth/login',json={'email':'a@example.com','password':'password123'}).status_code==200

def test_duplicate_registration(client):
    register(client)
    assert client.post('/auth/register',json={'name':'Alice','email':'a@example.com','password':'password123'}).status_code==409

def test_csv_end_to_end(client,db):
    token=register(client);headers={'Authorization':f'Bearer {token}'}
    wid=client.get('/workspaces',headers=headers).json()[0]['id']
    def post(k,text):
        return client.post(f'/workspaces/{wid}/import/{k}',headers=headers,files={'file':(f'{k}.csv',text,'text/csv')})
    products='sku,name,category,cost,price,stock\nP1,Shirt,Fashion,200,1000,20\n'
    orders='external_id,sku,purchased_at,quantity,unit_price,unit_cost,shipping,platform_fee,status\nO1,P1,'+datetime.utcnow().isoformat()+',2,1000,200,100,100,delivered\n'
    returns='external_id,order_external_id,reason,refunded_amount,return_shipping,restockable\nR1,O1,Size,2000,50,true\n'
    assert post('products',products).json()['imported']==1
    assert post('products',products).json()['skipped']==1
    assert post('orders',orders).json()['imported']==1
    assert post('returns',returns).json()['imported']==1
    k=client.get(f'/workspaces/{wid}/overview',headers=headers).json()['kpis']
    assert k['orders']==1 and k['gross_revenue']==2000 and k['refunds']==2000 and k['profit']==-650
    assert len(client.get(f'/workspaces/{wid}/returns',headers=headers).json())==1
    assert len(client.get(f'/workspaces/{wid}/inventory',headers=headers).json())==1
    assert len(client.get(f'/workspaces/{wid}/orders',headers=headers).json()['items'])==1
    assert 'profit' in client.post(f'/workspaces/{wid}/assistant',json={'question':'What is my profit?'},headers=headers).json()['answer'].lower()

def test_csv_validation_and_rollback(client,db):
    token=register(client);h={'Authorization':f'Bearer {token}'};wid=client.get('/workspaces',headers=h).json()[0]['id']
    resp=client.post(f'/workspaces/{wid}/import/products',headers=h,files={'file':('bad.csv','sku,name,category,cost,price,stock\nX,Alpha,Other,100,200,4\nY,Beta,Other,-1,200,4\n','text/csv')})
    assert resp.status_code==422
    assert client.get(f'/workspaces/{wid}/inventory',headers=h).json()==[]
    assert client.post(f'/workspaces/{wid}/import/orders',headers=h,files={'file':('bad.txt','bad','text/plain')}).status_code==422

def test_alert_duplicate_prevention(db):
    w=Workspace(name='Test');db.add(w);db.flush()
    p=Product(workspace_id=w.id,sku='X',name='Risky product',category='Home',cost=500,price=900,stock=30);db.add(p);db.flush()
    for i in range(10):
        o=Order(workspace_id=w.id,external_id=f'O{i}',product_id=p.id,purchased_at=datetime.utcnow()-timedelta(days=i),quantity=1,unit_price=900,unit_cost=500,shipping=80,platform_fee=70,status='delivered')
        db.add(o);db.flush()
        if i<5:db.add(Return(workspace_id=w.id,external_id=f'R{i}',order_id=o.id,reason='Damaged',refunded_amount=900,return_shipping=80))
    db.commit()
    first=detect_alerts(db,w.id);second=detect_alerts(db,w.id)
    assert len(first)>=1 and len(second)==0
    assert db.scalar(select(Alert).where(Alert.workspace_id==w.id)) is not None

def test_demo_is_read_only(client,db):
    wid=seed_demo(db)
    token=register(client)
    response=client.post(f'/workspaces/{wid}/import/products',headers={'Authorization':f'Bearer {token}'},files={'file':('products.csv','sku,name,category,cost,price,stock\nA,A,A,1,2,2\n','text/csv')})
    assert response.status_code==403
    overview=client.get(f'/workspaces/{wid}/overview')
    assert overview.status_code==200 and overview.json()['kpis']['orders']>1000
