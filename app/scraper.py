import re
import requests
from bs4 import BeautifulSoup
from app.database import SessionLocal, Winery, init_db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def parse_vino_svoe(db: SessionLocal):
    """Парсинг списка и детальных данных виноделен с vino-svoe.ru"""
    print("[*] Запуск скрапинга vino-svoe.ru...")
    url = "https://vino-svoe.ru/wineries"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            # Ищем Build ID для Nuxt Data
            build_match = re.search(r'/_nuxt/builds/meta/([a-f0-9\-]+)\.json', res.text)
            added = 0
            
            if build_match:
                build_id = build_match.group(1)
                data_url = f"https://vino-svoe.ru/_nuxt/builds/data/{build_id}/wineries.json"
                data_res = requests.get(data_url, headers=HEADERS, timeout=10)
                
                if data_res.status_code == 200:
                    json_data = data_res.json()
                    raw_items = json_data.get("data", []) or json_data.get("_payload", {}).get("data", [])
                    
                    for item in raw_items:
                        if isinstance(item, dict) and item.get("name"):
                            name = item.get("name").strip()
                            slug = item.get("slug") or item.get("id") or name.lower().replace(" ", "-")
                            
                            # Пробуем подтянуть детальное описание по слагу
                            detail_desc = item.get("description", "")
                            detail_url = f"https://vino-svoe.ru/wineries/{slug}"
                            
                            existing = db.query(Winery).filter(Winery.name == name).first()
                            if not existing:
                                db.add(Winery(
                                    slug=str(slug),
                                    name=name,
                                    region=item.get("region", "Россия"),
                                    description=detail_desc,
                                    website=item.get("website", detail_url),
                                    source_url=detail_url
                                ))
                                added += 1
                            elif not existing.description and detail_desc:
                                existing.description = detail_desc
                                existing.slug = str(slug)
                                existing.source_url = detail_url

            # Запасной вариант парсинга HTML ссылок
            soup = BeautifulSoup(res.text, "lxml")
            links = soup.select("a[href*='/wineries/']")
            for a in links:
                href = a.get("href", "")
                name = a.get_text(strip=True)
                if name and len(name) > 2 and len(name) < 70 and href != "/wineries":
                    slug = href.split("/")[-1]
                    existing = db.query(Winery).filter(Winery.name == name).first()
                    if not existing:
                        db.add(Winery(
                            slug=slug,
                            name=name,
                            region="Россия",
                            source_url=f"https://vino-svoe.ru{href}"
                        ))
                        added += 1
            
            db.commit()
            print(f"[✓] vino-svoe.ru: обработано {added} новых виноделен")
    except Exception as e:
        print(f"[!] Ошибка vino-svoe.ru: {e}")

def parse_vino_ru(db: SessionLocal):
    """Парсинг vino.ru"""
    print("[*] Запуск скрапинга vino.ru...")
    url = "https://vino.ru/atlas-rossiyskikh-vinodelen/letters/"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "lxml")
            items = soup.select("a[href*='/atlas-rossiyskikh-vinodelen/']")
            added = 0
            for item in items:
                name = item.get_text(strip=True)
                href = item.get("href", "")
                if name and len(name) > 2 and not name.startswith("Атлас") and href.count('/') > 3:
                    full_link = f"https://vino.ru{href}" if href.startswith('/') else href
                    slug = href.strip('/').split('/')[-1]
                    if not db.query(Winery).filter(Winery.name == name).first():
                        db.add(Winery(
                            slug=slug,
                            name=name,
                            region="Россия",
                            website=full_link,
                            source_url=url
                        ))
                        added += 1
            db.commit()
            print(f"[✓] vino.ru: обработано {added} новых виноделен")
    except Exception as e:
        print(f"[!] Ошибка vino.ru: {e}")

def seed_fallback_data(db: SessionLocal):
    """Обновленные начальные данные с детальными описаниями"""
    default_wineries = [
        {
            "slug": "51-parallel-winery",
            "name": "51 Parallel Winery",
            "region": "Краснодарский край",
            "description": "Инновационный проект, расположенный на 51-й параллели. Сочетание передовых технологий виноделия и особого микроклимата терруара.",
            "website": "https://vino-svoe.ru/wineries/51-parallel-winery"
        },
        {
            "slug": "abrau-durso",
            "name": "Абрау-Дюрсо",
            "region": "Краснодарский край (Новороссийск)",
            "description": "Легендарное винодельческое предприятие с более чем 150-летней историей. Специализируется на производстве премиальных классических и акратофорных игристых вин.",
            "website": "https://abraudurso.ru"
        },
        {
            "slug": "vedernikov",
            "name": "Винодельня Ведерниковъ",
            "region": "Ростовская область (Долина Дона)",
            "description": "Флагман донского автохтонного виноделия. Известна уникальными винами из аборигенных сортов винограда: Красностоп Золотовский, Сибирьковый и Цимлянский Чёрный.",
            "website": "https://vedernikovwine.ru"
        },
        {
            "slug": "chateau-de-talu",
            "name": "Château de Talu",
            "region": "Краснодарский край (Геленджик)",
            "description": "Современная винодельня премиум-класса, созданная по образу французских шато. Виноградники расположены на толстом мысе Геленджикской бухты.",
            "website": "https://chateaudetalu.ru"
        }
    ]
    
    for w in default_wineries:
        existing = db.query(Winery).filter(Winery.name == w["name"]).first()
        if not existing:
            db.add(Winery(**w))
        else:
            if not existing.description or len(existing.description) < 20:
                existing.description = w["description"]
                existing.slug = w["slug"]
    db.commit()

def run_scraper():
    init_db()
    db = SessionLocal()
    try:
        parse_vino_svoe(db)
        parse_vino_ru(db)
        seed_fallback_data(db)
    finally:
        db.close()

if __name__ == "__main__":
    run_scraper()
