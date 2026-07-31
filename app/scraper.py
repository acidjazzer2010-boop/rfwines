import requests
from bs4 import BeautifulSoup
from app.database import SessionLocal, Winery, init_db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*"
}

def parse_vino_svoe_nuxt(db: SessionLocal):
    """Быстрый парсинг vino-svoe.ru через Nuxt Data JSON"""
    print("[*] Парсинг vino-svoe.ru...")
    try:
        # 1. Получаем актуальный buildId
        meta_url = "https://vino-svoe.ru/_nuxt/builds/meta/eda8a7f0-aa81-4ec2-bb4a-8798f29e7ea7.json"
        res = requests.get(meta_url, headers=HEADERS, timeout=10)
        
        if res.status_code == 200:
            build_id = res.json().get("id", "eda8a7f0-aa81-4ec2-bb4a-8798f29e7ea7")
        else:
            build_id = "eda8a7f0-aa81-4ec2-bb4a-8798f29e7ea7"

        # 2. Запрашиваем JSON-данные страницы виноделен
        data_url = f"https://vino-svoe.ru/_nuxt/builds/data/{build_id}/wineries.json"
        data_res = requests.get(data_url, headers=HEADERS, timeout=10)

        if data_res.status_code == 200:
            json_data = data_res.json()
            # Извлекаем объекты (Nuxt упаковывает состояние в _payload или data)
            # Если структурированный JSON отдал список виноделен:
            items = json_data.get("data", []) or json_data.get("_payload", {}).get("data", [])
            
            added_count = 0
            for item in items:
                if isinstance(item, dict) and "name" in item:
                    name = item.get("name")
                    region = item.get("region", "Россия")
                    desc = item.get("description", "")
                    site = item.get("website", "")

                    if name and not db.query(Winery).filter(Winery.name == name).first():
                        winery = Winery(
                            name=name,
                            region=region,
                            description=desc,
                            website=site,
                            source_url="https://vino-svoe.ru"
                        )
                        db.add(winery)
                        added_count += 1
            
            db.commit()
            print(f"[✓] vino-svoe.ru: добавлено {added_count} виноделен")
        else:
            print(f"[!] Не удалось загрузить JSON данных: статус {data_res.status_code}")

    except Exception as e:
        print(f"[!] Ошибка при обработке vino-svoe.ru: {e}")


def parse_vino_ru_atlas(db: SessionLocal):
    """Парсинг алфавитного каталога vino.ru"""
    print("[*] Парсинг vino.ru...")
    url = "https://vino.ru/atlas-rossiyskikh-vinodelen/letters/"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "lxml")
            # Ищем все ссылки на карточки виноделен в алфавитном указателе
            links = soup.select("a[href*='/atlas-rossiyskikh-vinodelen/']")
            
            added_count = 0
            for link in links:
                name = link.get_text(strip=True)
                href = link.get("href", "")
                
                # Фильтруем технические ссылки
                if name and not name.startswith("Атлас") and len(name) < 80:
                    full_url = f"https://vino.ru{href}" if href.startswith("/") else href
                    
                    if not db.query(Winery).filter(Winery.name == name).first():
                        winery = Winery(
                            name=name,
                            region="Россия",
                            website=full_url,
                            source_url="https://vino.ru"
                        )
                        db.add(winery)
                        added_count += 1
            
            db.commit()
            print(f"[✓] vino.ru: добавлено {added_count} виноделен")
    except Exception as e:
        print(f"[!] Ошибка при обработке vino.ru: {e}")


def run_scraper():
    init_db()
    db = SessionLocal()
    try:
        parse_vino_svoe_nuxt(db)
        parse_vino_ru_atlas(db)
    finally:
        db.close()


if __name__ == "__main__":
    run_scraper()
