from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:///./data/wines.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Winery(Base):
    __tablename__ = "wineries"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True, nullable=True) # Уникальный слаг (напр. 51-parallel-winery)
    name = Column(String, unique=True, index=True, nullable=False)
    region = Column(String, index=True)
    description = Column(Text, nullable=True)
    website = Column(String, nullable=True)
    source_url = Column(String, nullable=True)

    wines = relationship("Wine", back_populates="winery")

class Wine(Base):
    __tablename__ = "wines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    grape_variety = Column(String, nullable=True)
    wine_type = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    winery_id = Column(Integer, ForeignKey("wineries.id"))

    winery = relationship("Winery", back_populates="wines")

def init_db():
    import os
    os.makedirs("./data", exist_ok=True)
    
    # Если структура изменилась, при необходимости можно пересоздать файл БД
    db_file = "./data/wines.db"
    
    # Создаем таблицы
    Base.metadata.create_all(bind=engine)
