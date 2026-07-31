from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:///./data/wines.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Winery(Base):
    __tablename__ = "wineries"

    id = Column(Integer, primary_key=True, index=True)
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
    wine_type = Column(String, nullable=True) # Красное, Белое, Игристое и т.д.
    year = Column(Integer, nullable=True)
    winery_id = Column(Integer, ForeignKey("wineries.id"))

    winery = relationship("Winery", back_populates="wines")

def init_db():
    import os
    os.makedirs("./data", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    
    # Автоматическое наполнение базовыми данными при первом запуске
    db = SessionLocal()
    try:
        if db.query(Winery).count() == 0:
            initial_wineries = [
                Winery(
                    name="Абрау-Дюрсо",
                    region="Краснодарский край (Новороссийск)",
                    description="Один из старейших и крупнейших производителей игристых и тихих вин в России.",
                    website="https://abraudurso.ru"
                ),
                Winery(
                    name="Усадьба Дивноморское",
                    region="Краснодарский край (Геленджик)",
                    description="Премиальное винодельческое хозяйство на берегу Чёрного моря.",
                    website="https://usadba-divnomorskoe.ru"
                ),
                Winery(
                    name="Винодельня Ведерниковъ",
                    region="Ростовская область (Долина Дона)",
                    description="Флагман донского автохтонного виноделия (Красностоп Золотовский, Сибирьковый).",
                    website="https://vedernikovwine.ru"
                ),
                Winery(
                    name="Золотая Балка",
                    region="Крым (Севастополь)",
                    description="Крупный производитель игристых и тихих вин в Балаклавской долине.",
                    website="https://zolotayabalka.ru"
                ),
                Winery(
                    name="Château de Talu",
                    region="Краснодарский край (Геленджик)",
                    description="Современная винодельня в французском стиле на побережье Чёрного моря.",
                    website="https://chateaudetalu.ru"
                )
            ]
            db.add_all(initial_wineries)
            db.commit()
            print("[✓] Базовые данные виноделен успешно загружены!")
    except Exception as e:
        print(f"[!] Ошибка инициализации базовых данных: {e}")
    finally:
        db.close()
