"""ProfitLens configuration, persistence, authentication, and domain models."""
from __future__ import annotations
import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, ForeignKey, String, Integer, Float, DateTime, Boolean, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from fastapi import HTTPException, Depends, Header
from sqlalchemy.orm import Session

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./profitlens.db')
if DATABASE_URL.startswith('sqlite:///'):
    db_file = DATABASE_URL.replace('sqlite:///', '', 1)
    if db_file != ':memory:': Path(db_file).parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite:') else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
SECRET = os.getenv('APP_SECRET', 'development-only-change-this-before-deployment')

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
class Workspace(Base):
    __tablename__ = 'workspaces'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    owner_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
class Product(Base):
    __tablename__ = 'products'
    __table_args__ = (UniqueConstraint('workspace_id', 'sku'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey('workspaces.id'), index=True)
    sku: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(180))
    category: Mapped[str] = mapped_column(String(80), default='Other')
    cost: Mapped[float] = mapped_column(Float, default=0)
    price: Mapped[float] = mapped_column(Float, default=0)
    stock: Mapped[int] = mapped_column(Integer, default=0)
class Order(Base):
    __tablename__ = 'orders'
    __table_args__ = (UniqueConstraint('workspace_id', 'external_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey('workspaces.id'), index=True)
    external_id: Mapped[str] = mapped_column(String(90))
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), index=True)
    purchased_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)
    unit_cost: Mapped[float] = mapped_column(Float)
    shipping: Mapped[float] = mapped_column(Float, default=0)
    platform_fee: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(30), default='delivered')
    product: Mapped[Product] = relationship()
class Return(Base):
    __tablename__ = 'returns'
    __table_args__ = (UniqueConstraint('workspace_id', 'external_id'), UniqueConstraint('order_id'))
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey('workspaces.id'), index=True)
    external_id: Mapped[str] = mapped_column(String(90))
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'), index=True)
    reason: Mapped[str] = mapped_column(String(100))
    refunded_amount: Mapped[float] = mapped_column(Float)
    return_shipping: Mapped[float] = mapped_column(Float, default=0)
    restockable: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    order: Mapped[Order] = relationship()
class Alert(Base):
    __tablename__ = 'alerts'
    __table_args__ = (UniqueConstraint('workspace_id', 'alert_key'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey('workspaces.id'), index=True)
    alert_key: Mapped[str] = mapped_column(String(180))
    kind: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(15), default='warning')
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(String(500))
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 250_000).hex()
    return f'{salt}${derived}'
def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split('$', 1)
        candidate = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 250_000).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError): return False

def make_token(user_id: int) -> str:
    expires = int(time.time()) + 60 * 60 * 24 * 7
    payload = f'{user_id}.{expires}'
    signature = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f'{payload}.{signature}'
def parse_token(token: str) -> int:
    try:
        id_str, exp_str, sig = token.split('.')
        payload = f'{id_str}.{exp_str}'
        expected = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected) or int(exp_str) < time.time(): raise ValueError('expired')
        return int(id_str)
    except (ValueError, AttributeError): raise HTTPException(401, 'Invalid or expired session')

def get_db():
    with SessionLocal() as session: yield session

def current_user(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith('Bearer '): raise HTTPException(401, 'Sign in to access your workspace')
    user = db.get(User, parse_token(authorization[7:]))
    if not user: raise HTTPException(401, 'Account unavailable')
    return user

def authorized_workspace(db: Session, user: User | None, workspace_id: int) -> Workspace:
    ws = db.get(Workspace, workspace_id)
    if not ws or (not ws.is_demo and (user is None or ws.owner_id != user.id)):
        raise HTTPException(404, 'Workspace not found')
    return ws
