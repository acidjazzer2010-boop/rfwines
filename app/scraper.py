import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from app.database import SessionLocal, Winery, init_db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def parse_vino_svoe(db: Session):
    """Парсинг списка виноделен с сайта vino-svoe.ru"""
    url = "https://vino-svoe.ru/wineries"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "lxml")
            # Пример парсинга блоков виноделен (структуру необходимо уточнять по HTML-коду страницы)
            cards = soup.find_all("div", class_="winery-card") or soup.find_all("a", class_="card")
            
            for card in cards:
                name = card.get_text(strip=True)
                if name:
                    existing = db.query(Winery).filter(Winery.name == name).first()
                    if not existing:
                        winery = Winery(
                            name=name,
                            region="Россия",
                            source_url=url
                        )
                        db.add(winery)
            db.commit()
            print("[✓] Данные с vino-svoe.ru обработаны")
    except Exception as e:
        print(f"[!] Ошибка при парсинге vino-svoe.ru: {e}")

def run_scraper():
    init_db()
    db = SessionLocal()
    try:
        parse_vino_svoe(db)
    finally:
        db.close()

if __name__ == "__main__":
    run_scraper()
