from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import SessionLocal, init_db, Winery as WineryDB, Wine as WineDB
from pydantic import BaseModel

app = FastAPI(
    title="Российское Виноделие — API",
    description="API каталога российских виноделен и вин",
    version="1.1.0"
)

@app.on_event("startup")
def on_startup():
    init_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class WineSchema(BaseModel):
    id: int
    name: str
    grape_variety: Optional[str] = None
    wine_type: Optional[str] = None
    year: Optional[int] = None

    class Config:
        from_attributes = True

class WinerySchema(BaseModel):
    id: int
    slug: Optional[str] = None
    name: str
    region: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    source_url: Optional[str] = None
    wines: List[WineSchema] = []

    class Config:
        from_attributes = True

@app.get("/")
def root():
    return {"message": "API Каталога Вин и Виноделен России работает!"}

@app.get("/wineries", response_model=List[WinerySchema])
def get_wineries(
    region: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(WineryDB)
    if region:
        query = query.filter(WineryDB.region.ilike(f"%{region}%"))
    if search:
        query = query.filter(WineryDB.name.ilike(f"%{search}%"))
    return query.all()

@app.get("/wineries/{winery_id_or_slug}", response_model=WinerySchema)
def get_winery(winery_id_or_slug: str, db: Session = Depends(get_db)):
    # Поиск по ID или по Slug
    if winery_id_or_slug.isdigit():
        winery = db.query(WineryDB).filter(WineryDB.id == int(winery_id_or_slug)).first()
    else:
        winery = db.query(WineryDB).filter(WineryDB.slug == winery_id_or_slug).first()
        
    if not winery:
        raise HTTPException(status_code=404, detail="Винодельня не найдена")
    return winery
