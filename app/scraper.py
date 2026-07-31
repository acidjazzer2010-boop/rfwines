import re
import requests
from bs4 import BeautifulSoup
from app.database import SessionLocal, Winery, init_db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
}

def fetch_full_description_vino_svoe(build_id: str, slug: str) -> str:
    """Загрузка полного текста описания страницы конкретной винодельни через Nuxt JSON"""
    try:
        url = f"https://vino-svoe.ru/_nuxt/builds/data/{build_id}/wineries/{slug}.json"
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            data = res.json()
            # Проходим по объектам Nuxt Payload и ищем текст описания
            payload = data.get("_payload", {}) or data
            for val in payload.values() if isinstance(payload, dict) else []:
                if isinstance(val, dict):
                    desc = val.get("description") or val.get("about") or val.get("text")
                    if desc and isinstance(desc, str) and len(desc) > 30:
                        return desc.strip()
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            desc = item.get("description") or item.get("about") or item.get("text")
                            if desc and isinstance(desc, str) and len(desc) > 30:
                                return desc.strip()
    except Exception:
        pass
    return ""

def parse_vino_svoe(db: SessionLocal):
    """Парсинг виноделен с глубокой выгрузкой полных описаний"""
    print("[*] Запуск глубокого скрапинга vino-svoe.ru...")
    url = "https://vino-svoe.ru/wineries"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
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
                            raw_slug = item.get("slug") or item.get("id") or name.lower().replace(" ", "-")
                            slug = str(raw_slug).strip().lower()
                            
                            # Получаем сначала базовое описание из списка
                            desc = item.get("description", "") or item.get("shortDescription", "")
                            
                            # Если базовое описание короткое/пустое, запрашиваем детальный текст со страницы винодельни
                            if not desc or len(desc) < 40:
                                full_desc = fetch_full_description_vino_svoe(build_id, slug)
                                if full_desc:
                                    desc = full_desc

                            detail_url = f"https://vino-svoe.ru/wineries/{slug}"
                            
                            existing = db.query(Winery).filter(
                                (Winery.name == name) | (Winery.slug == slug)
                            ).first()
                            
                            if not existing:
                                db.add(Winery(
                                    slug=slug,
                                    name=name,
                                    region=item.get("region", "Россия"),
                                    description=desc,
                                    website=item.get("website", detail_url),
                                    source_url=detail_url
                                ))
                                added += 1
                            else:
                                if desc and len(desc) > len(existing.description or ""):
                                    existing.description = desc
                                if not existing.slug:
                                    existing.slug = slug

            db.commit()
            print(f"[✓] vino-svoe.ru: обработано {added} виноделен")
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
            
            db.commit()
            print(f"[✓] vino.ru: обработано {added} виноделен")
    except Exception as e:
        print(f"[!] Ошибка vino.ru: {e}")

def seed_fallback_data(db: SessionLocal):
    """Полноценные тексты описаний для ключевых производителей"""
    default_wineries = [
        {
            "slug": "51-parallel-winery",
            "name": "51 Parallel Winery",
            "region": "Краснодарский край",
            "description": "51 Parallel Winery — динамично развивающийся винодельческий проект на терруарах Северо-Западного Кавказа. Название связано с географическим расположением виноградников, микроклимат которых создает уникальные условия для вызревания классических сортов винограда Каберне Совиньон, Мерло и Шардоне.",
            "website": "https://vino-svoe.ru/wineries/51-parallel-winery"
        },
        {
            "slug": "abrau-durso",
            "name": "Абрау-Дюрсо",
            "region": "Краснодарский край (Новороссийск)",
            "description": "Русский винный дом «Абрау-Дюрсо» — ведущий производитель игристых и тихих вин России. Имение было основано в 1870 году по указу императора Александра II. Сегодня «Абрау-Дюрсо» выпускает высококлассные игристые вина, созданные как по классическому французскому методу Шампенуаз с выдержкой в горных тоннелях, так и по методу Шарма.",
            "website": "https://abraudurso.ru"
        },
        {
            "slug": "vedernikov",
            "name": "Винодельня Ведерниковъ",
            "region": "Ростовская область (Долина Дона)",
            "description": "Винодельня «Ведерниковъ» — пионер и признанный лидер в восстановлении и производстве вин из автохтонных (аборигенных) сортов винограда Дона. Хозяйство расположено в хуторе Ведерников. Ключевые сортовые визитные карточки — Красностоп Золотовский, Сибирьковый и Цимлянский Чёрный.",
            "website": "https://vedernikovwine.ru"
        },
        {
            "slug": "chateau-de-talu",
            "name": "Château de Talu",
            "region": "Краснодарский край (Геленджик)",
            "description": "Château de Talu — одна из самых живописных и современных виноделен Краснодарского края, основанная в 2005 году. Производственный комплекс построен в классическом французском стиле. Виноградники расположены на Толстом мысе Геленджикской бухты, где морской бриз и мергелевые почвы придают винам яркую минеральность и свежесть.",
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
            if not existing.description or len(existing.description) < 50:
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
