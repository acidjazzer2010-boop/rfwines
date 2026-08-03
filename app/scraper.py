import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.database import SessionLocal, Winery, init_db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
}

def fetch_description_worker(item_data):
    """Фоновый поток для быстрого получения описания одной винодельни"""
    build_id, slug, current_desc = item_data
    if current_desc and len(current_desc) > 50:
        return slug, current_desc

    try:
        # 1. Запрос к детальному JSON Nuxt
        url = f"https://vino-svoe.ru/_nuxt/builds/data/{build_id}/wineries/{slug}.json"
        res = requests.get(url, headers=HEADERS, timeout=4)
        if res.status_code == 200:
            data = res.json()
            payload = data.get("_payload", {}) or data
            
            # Рекурсивный поиск самого длинного текста в JSON
            candidates = []
            def search_text(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k in ["description", "about", "text", "content", "story"] and isinstance(v, str) and len(v) > 30:
                            candidates.append(v)
                        else:
                            search_text(v)
                elif isinstance(obj, list):
                    for elem in obj:
                        search_text(elem)
            
            search_text(payload)
            if candidates:
                return slug, max(candidates, key=len).strip()

        # 2. Запасной забор текста прямо из HTML страницы
        html_url = f"https://vino-svoe.ru/wineries/{slug}"
        res_html = requests.get(html_url, headers=HEADERS, timeout=4)
        if res_html.status_code == 200:
            soup = BeautifulSoup(res_html.text, "lxml")
            paragraphs = [p.get_text(strip=True) for p in soup.find_all(["p", "div"]) if len(p.get_text(strip=True)) > 50]
            if paragraphs:
                return slug, max(paragraphs, key=len).strip()
    except Exception:
        pass

    return slug, current_desc or ""

def parse_vino_svoe(db: SessionLocal):
    """Парсинг виноделен и параллельный сбор полных описаний"""
    print("[*] Запуск скрапинга vino-svoe.ru...")
    url = "https://vino-svoe.ru/wineries"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            build_match = re.search(r'/_nuxt/builds/meta/([a-f0-9\-]+)\.json', res.text)
            
            if build_match:
                build_id = build_match.group(1)
                data_url = f"https://vino-svoe.ru/_nuxt/builds/data/{build_id}/wineries.json"
                data_res = requests.get(data_url, headers=HEADERS, timeout=10)
                
                if data_res.status_code == 200:
                    json_data = data_res.json()
                    raw_items = json_data.get("data", []) or json_data.get("_payload", {}).get("data", [])
                    
                    tasks = []
                    wineries_to_add = []
                    
                    for item in raw_items:
                        if isinstance(item, dict) and item.get("name"):
                            name = item.get("name").strip()
                            raw_slug = item.get("slug") or item.get("id") or name.lower().replace(" ", "-")
                            slug = str(raw_slug).strip().lower()
                            desc = item.get("description", "") or item.get("about", "")
                            
                            wineries_to_add.append({
                                "slug": slug,
                                "name": name,
                                "region": item.get("region", "Россия"),
                                "website": item.get("website", f"https://vino-svoe.ru/wineries/{slug}"),
                                "source_url": f"https://vino-svoe.ru/wineries/{slug}",
                                "description": desc
                            })
                            tasks.append((build_id, slug, desc))

                    # Запуск многопоточной загрузки описаний (10 потоков)
                    print(f"[*] Загрузка полных описаний для {len(tasks)} виноделен в 10 потоков...")
                    descriptions_map = {}
                    with ThreadPoolExecutor(max_workers=10) as executor:
                        future_to_slug = {executor.submit(fetch_description_worker, task): task[1] for task in tasks}
                        for future in as_completed(future_to_slug):
                            slug, full_desc = future.result()
                            if full_desc:
                                descriptions_map[slug] = full_desc

                    # Сохранение в базу данных
                    added = 0
                    for w in wineries_to_add:
                        slug = w["slug"]
                        final_desc = descriptions_map.get(slug) or w["description"]
                        
                        existing = db.query(Winery).filter(
                            (Winery.name == w["name"]) | (Winery.slug == slug)
                        ).first()
                        
                        if not existing:
                            db.add(Winery(
                                slug=slug,
                                name=w["name"],
                                region=w["region"],
                                description=final_desc,
                                website=w["website"],
                                source_url=w["source_url"]
                            ))
                            added += 1
                        else:
                            if final_desc and len(final_desc) > len(existing.description or ""):
                                existing.description = final_desc
                            if not existing.slug:
                                existing.slug = slug

                    db.commit()
                    print(f"[✓] vino-svoe.ru: успешно спарсено {added} виноделен с описаниями!")
    except Exception as e:
        print(f"[!] Ошибка vino-svoe.ru: {e}")

def parse_vino_ru(db: SessionLocal):
    """Парсинг каталога vino.ru"""
    print("[*] Запуск скрапинга vino.ru...")
    url = "https://vino.ru/atlas-rossiyskikh-vinodelen/letters/"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
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
            print(f"[✓] vino.ru: успешно спарсено {added} виноделен")
    except Exception as e:
        print(f"[!] Ошибка vino.ru: {e}")

def seed_fallback_data(db: SessionLocal):
    """Гарантированные описания для базовых виноделен"""
    default_wineries = [
        {
            "slug": "51-parallel-winery",
            "name": "51 Parallel Winery",
            "region": "Краснодарский край",
            "description": "51 Parallel Winery — динамично развивающийся винодельческий проект на терруарах Северо-Западного Кавказа. Название связано с географическим расположением виноградников.",
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
            "description": "Винодельня «Ведерниковъ» — пионер и признанный лидер в восстановлении и производстве вин из автохтонных сортов винограда Дона.",
            "website": "https://vedernikovwine.ru"
        },
        {
            "slug": "chateau-de-talu",
            "name": "Château de Talu",
            "region": "Краснодарский край (Геленджик)",
            "description": "Château de Talu — одна из самых живописных и современных виноделен Краснодарского края в французском стиле.",
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
            if not existing.description or len(existing.description) < 30:
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
