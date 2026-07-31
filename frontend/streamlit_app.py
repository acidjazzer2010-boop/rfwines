import streamlit as st
import requests
import pandas as pd

API_URL = "https://rfwines-backend.onrender.com"

st.set_page_config(
    page_title="Атлас Виноделен России",
    page_icon="🍷",
    layout="wide"
)

st.title("🍷 Атлас и Каталог Виноделен России")
st.markdown("Интерактивный справочник российских производителей вина.")

# Боковое меню (Фильтры)
st.sidebar.header("Фильтры и Поиск")
search_query = st.sidebar.text_input("Поиск по названию винодельни:")

# Загрузка данных с FastAPI
@st.cache_data(ttl=60)
def fetch_wineries(search: str = ""):
    try:
        params = {}
        if search:
            params["search"] = search
        res = requests.get(f"{API_URL}/wineries", params=params)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        st.error(f"Не удалось подключиться к API backend: {e}")
    return []

wineries = fetch_wineries(search_query)

# Отображение
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader(f"Найдено виноделен: {len(wineries)}")
    selected_winery_name = st.radio(
        "Выберите винодельню:",
        options=[w["name"] for w in wineries] if wineries else ["Нет данных"]
    )

with col2:
    if wineries and selected_winery_name != "Нет данных":
        selected_winery = next(w for w in wineries if w["name"] == selected_winery_name)
        
        st.header(selected_winery["name"])
        st.write(f"**Регион:** {selected_winery.get('region') or 'Не указан'}")
        
        if selected_winery.get("website"):
            st.markdown(f"[Официальный сайт]({selected_winery['website']})")
            
        st.markdown("### Описание")
        st.write(selected_winery.get("description") or "Описание пока не добавлено.")

        st.markdown("### Вина производителя")
        wines = selected_winery.get("wines", [])
        if wines:
            df_wines = pd.DataFrame(wines)
            st.dataframe(df_wines, use_container_width=True)
        else:
            st.info("Список вин для данной винодельни пока пуст.")
