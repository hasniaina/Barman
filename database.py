import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

DB_FILE = "stock.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

# Engine SQLite optimise pour les acces concourants légers
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

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
# 2. Routes Backend dans main.py

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
    """Crée les tables manquantes dans stock.db sans écraser les données existantes."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Generateur de session BDD pour l'injection de dependance FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

