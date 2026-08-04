import re
import requests
from bs4 import BeautifulSoup
from app.database import SessionLocal, Winery, init_db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

# Известные версии сборки Nuxt 3 (прямой доступ к статике без блокировки Cloudflare)
FALLBACK_BUILD_IDS = [
    "eda8a7f0-aa81-4ec2-bb4a-8798f29e7ea7"
]

def get_nuxt_build_id():
    """Пытается вытащить ID сборки из HTML, либо использует гарантированный fallback"""
    try:
        res = requests.get("https://vino-svoe.ru/wineries", headers=HEADERS, timeout=5)
        if res.status_code == 200:
            match = re.search(r'/_nuxt/builds/meta/([a-f0-9\-]+)\.json', res.text)
            if match:
                return match.group(1)
    except Exception:
        pass
    return FALLBACK_BUILD_IDS[0]

def parse_vino_svoe(db: SessionLocal):
    """Прямой сбор каталога из статического JSON Nuxt 3"""
    print("[*] Запуск скрапинга vino-svoe.ru...")
    build_id = get_nuxt_build_id()
    
    # Пробуем варианты прямых URL с данными
    urls_to_try = [
        f"https://vino-svoe.ru/_nuxt/builds/data/{build_id}/wineries.json",
        f"https://vino-svoe.ru/_nuxt/builds/data/{FALLBACK_BUILD_IDS[0]}/wineries.json"
    ]
    
    raw_items = []
    for data_url in urls_to_try:
        try:
            res = requests.get(data_url, headers=HEADERS, timeout=8)
            if res.status_code == 200:
                json_data = res.json()
                if isinstance(json_data, dict):
                    raw_items = json_data.get("data", []) or json_data.get("_payload", {}).get("data", [])
                    if not raw_items and "_payload" in json_data:
                        raw_items = [v for v in json_data["_payload"].values() if isinstance(v, dict) and "name" in v]
                elif isinstance(json_data, list):
                    raw_items = json_data
                
                if raw_items:
                    break
        except Exception as e:
            print(f"[!] Ошибка запроса к {data_url}: {e}")
            
    added = 0
    if raw_items:
        for item in raw_items:
            if isinstance(item, dict) and item.get("name"):
                try:
                    name = str(item.get("name")).strip()
                    if not name or name == "None":
                        continue
                        
                    raw_slug = item.get("slug") or item.get("id") or name.lower().replace(" ", "-")
                    slug = str(raw_slug).strip().lower()
                    
                    desc = str(item.get("description") or item.get("about") or item.get("shortDescription") or "").strip()
                    if desc == "None":
                        desc = ""
                        
                    region = str(item.get("region") or "Россия").strip()
                    website = str(item.get("website") or f"https://vino-svoe.ru/wineries/{slug}").strip()
                    
                    existing = db.query(Winery).filter(
                        (Winery.name == name) | (Winery.slug == slug)
                    ).first()
                    
                    if not existing:
                        db.add(Winery(
                            slug=slug,
                            name=name,
                            region=region,
                            description=desc,
                            website=website,
                            source_url=f"https://vino-svoe.ru/wineries/{slug}"
                        ))
                        added += 1
                    else:
                        if desc and len(desc) > len(existing.description or ""):
                            existing.description = desc
                        if not existing.slug:
                            existing.slug = slug
                except Exception:
                    continue
        db.commit()
        print(f"[✓] vino-svoe.ru: успешно добавлено/обновлено {added} виноделен")

def parse_vino_ru(db: SessionLocal):
    """Парсинг каталога vino.ru"""
    print("[*] Запуск скрапинга vino.ru...")
    url = "https://vino.ru/atlas-rossiyskikh-vinodelen/letters/"
    try:
        res = requests.get(url, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "lxml")
            items = soup.select("a[href*='/atlas-rossiyskikh-vinodelen/']")
            added = 0
            for item in items:
                try:
                    name = item.get_text(strip=True)
                    href = item.get("href", "")
                    if name and len(name) > 2 and not name.startswith("Атлас") and href.count('/') > 3:
                        full_link = f"https://vino.ru{href}" if href.startswith('/') else href
                        slug = href.strip('/').split('/')[-1].strip().lower()
                        
                        existing = db.query(Winery).filter(
                            (Winery.name == name) | (Winery.slug == slug)
                        ).first()
                        
                        if not existing:
                            db.add(Winery(
                                slug=slug,
                                name=name,
                                region="Россия",
                                website=full_link,
                                source_url=url
                            ))
                            added += 1
                        else:
                            if not existing.website:
                                existing.website = full_link
                except Exception:
                    continue
            
            db.commit()
            print(f"[✓] vino.ru: успешно добавлено {added} виноделен")
    except Exception as e:
        print(f"[!] Ошибка vino.ru: {e}")

def seed_fallback_data(db: SessionLocal):
    """Гарантированные данные базовых виноделен"""
    default_wineries = [
        {
            "slug": "51-parallel-winery",
            "name": "51 Parallel Winery",
            "region": "Краснодарский край",
            "description": "Инновационный винодельческий проект на 51-й параллели с уникальным терруаром.",
            "website": "https://vino-svoe.ru/wineries/51-parallel-winery"
        },
        {
            "slug": "abrau-durso",
            "name": "Абрау-Дюрсо",
            "region": "Краснодарский край (Новороссийск)",
            "description": "Русский винный дом «Абрау-Дюрсо» — ведущий производитель игристых и тихих вин России с историей с 1870 года.",
            "website": "https://abraudurso.ru"
        },
        {
            "slug": "vedernikov",
            "name": "Винодельня Ведерниковъ",
            "region": "Ростовская область (Долина Дона)",
            "description": "Флагман донского автохтонного виноделия (Красностоп Золотовский, Сибирьковый).",
            "website": "https://vedernikovwine.ru"
        },
        {
            "slug": "chateau-de-talu",
            "name": "Château de Talu",
            "region": "Краснодарский край (Геленджик)",
            "description": "Премиальное винодельческое хозяйство в французском стиле на берегу Чёрного моря.",
            "website": "https://chateaudetalu.ru"
        }
    ]
    
    for w in default_wineries:
        existing = db.query(Winery).filter(
            (Winery.name == w["name"]) | (Winery.slug == w["slug"])
        ).first()
        if not existing:
            db.add(Winery(**w))
        else:
            if not existing.description or len(existing.description) < 20:
                existing.description = w["description"]
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
