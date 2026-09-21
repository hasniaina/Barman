import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

# Récupération de l'URL depuis l'environnement (Render) ou fallback sur SQLite local
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./stock.db")

# Correction de la compatibilité pour SQLAlchemy (postgres:// -> postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configuration dynamique du moteur selon le type de base
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    table_number = Column(Integer, nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity = Column(Integer, default=1)
    price_at_sale = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    item = relationship("Item")

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    quantity = Column(Integer, default=0)
    price = Column(Float, nullable=False)
    snack = Column(Boolean, default=True)

class SaleHistory(Base):
    __tablename__ = "sales_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    table_number = Column(Integer, nullable=False)
    item_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    price_at_sale = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    """Crée les tables manquantes sans écraser les données existantes."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Générateur de session BDD pour l'injection de dépendances FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()