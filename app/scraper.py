import re
import requests
from bs4 import BeautifulSoup
from app.database import SessionLocal, Winery, init_db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
}

def parse_vino_svoe(db: SessionLocal):
    """Парсинг vino-svoe.ru с динамическим поиском Nuxt Build ID"""
    print("[*] Запуск скрапинга vino-svoe.ru...")
    try:
        url = "https://vino-svoe.ru/wineries"
        res = requests.get(url, headers=HEADERS, timeout=10)
        
        if res.status_code == 200:
            # 1. Пытаемся вытащить buildId из HTML
            build_match = re.search(r'/_nuxt/builds/meta/([a-f0-9\-]+)\.json', res.text)
            added = 0
            
            if build_match:
                build_id = build_match.group(1)
                data_url = f"https://vino-svoe.ru/_nuxt/builds/data/{build_id}/wineries.json"
                data_res = requests.get(data_url, headers=HEADERS, timeout=10)
                
                if data_res.status_code == 200:
                    json_data = data_res.json()
                    # Обход структуры Nuxt Payload
                    raw_items = json_data.get("data", []) or json_data.get("_payload", {}).get("data", [])
                    
                    for item in raw_items:
                        if isinstance(item, dict) and item.get("name"):
                            name = item.get("name").strip()
                            if name and not db.query(Winery).filter(Winery.name == name).first():
                                db.add(Winery(
                                    name=name,
                                    region=item.get("region", "Россия"),
                                    description=item.get("description", ""),
                                    website=item.get("website", ""),
                                    source_url=url
                                ))
                                added += 1
            
            # 2. Если Nuxt JSON не отдал данные, парсим теги прямо из HTML
            if added == 0:
                soup = BeautifulSoup(res.text, "lxml")
                links = soup.select("a[href*='/wineries/']")
                for a in links:
                    name = a.get_text(strip=True)
                    if name and len(name) > 2 and len(name) < 70:
                        if not db.query(Winery).filter(Winery.name == name).first():
                            db.add(Winery(name=name, region="Россия", source_url=url))
                            added += 1
            
            db.commit()
            print(f"[✓] vino-svoe.ru: успешно добавлено {added} виноделен")
    except Exception as e:
        print(f"[!] Ошибка vino-svoe.ru: {e}")


def parse_vino_ru(db: SessionLocal):
    """Парсинг алфавитного каталога vino.ru"""
    print("[*] Запуск скрапинга vino.ru...")
    url = "https://vino.ru/atlas-rossiyskikh-vinodelen/letters/"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "lxml")
            added = 0
            
            # Поиск всех карточек/ссылок на отдельные винодельни
            items = soup.select("a[href*='/atlas-rossiyskikh-vinodelen/']")
            for item in items:
                name = item.get_text(strip=True)
                href = item.get("href", "")
                
                # Исключаем навигационные и буквенные ссылки
                if name and len(name) > 2 and not name.startswith("Атлас") and href.count('/') > 3:
                    full_link = f"https://vino.ru{href}" if href.startswith('/') else href
                    if not db.query(Winery).filter(Winery.name == name).first():
                        db.add(Winery(
                            name=name,
                            region="Россия",
                            website=full_link,
                            source_url=url
                        ))
                        added += 1
            
            db.commit()
            print(f"[✓] vino.ru: успешно добавлено {added} виноделен")
    except Exception as e:
        print(f"[!] Ошибка vino.ru: {e}")


def seed_fallback_data(db: SessionLocal):
    """Гарантированные базовые данные, чтобы кагалог никогда не был пустым"""
    if db.query(Winery).count() == 0:
        print("[*] Наполнение базы fallback-данными...")
        default_wineries = [
            Winery(name="Абрау-Дюрсо", region="Краснодарский край", description="Флагман российского игристого виноделия", website="https://abraudurso.ru"),
            Winery(name="Винодельня Ведерниковъ", region="Ростовская область", description="Автохтонное виноделие Долина Дона", website="https://vedernikovwine.ru"),
            Winery(name="Усадьба Дивноморское", region="Краснодарский край", description="Премиальное терруарное виноделие", website="https://usadba-divnomorskoe.ru"),
            Winery(name="Золотая Балка", region="Крым (Севастополь)", description="Винодельческий комплекс Балаклавы", website="https://zolotayabalka.ru"),
            Winery(name="Château de Talu", region="Краснодарский край", description="Французский стиль на берегу Чёрного моря", website="https://chateaudetalu.ru"),
            Winery(name="Инкирман", region="Крым", description="Инкерманский завод маркерных вин", website="https://inkerman.ru"),
            Winery(name="Массандра", region="Крым", description="Ялтинское легендарное предприятие", website="https://massandra.su"),
            Winery(name="Фанагория", region="Краснодарский край", description="Один из крупнейших производителей полного цикла", website="https://fanagoria.ru")
        ]
        db.add_all(default_wineries)
        db.commit()
        print("[✓] Fallback данные успешно загружены")


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
