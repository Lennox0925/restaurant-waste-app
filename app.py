import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection  # 引入 Google Sheets 連結器
import os

# --- 設定頁面與樣式 ---
st.set_page_config(page_title="餐廳雲端報廢系統", layout="centered")

# Google Sheets 連結設定 (請將此網址替換為您的試算表網址)
# 建議將此網址放在 Streamlit Cloud 的 Secrets 設定中
SHEET_URL = "docs.google.com"

# 建立連線
conn = st.connection("gsheets", type=GSheetsConnection)

def get_taiwan_time():
    return datetime.utcnow() + timedelta(hours=8)

# --- 讀取選單資料 (維持讀取 menu.csv) ---
MENU_FILE = 'menu.csv'
@st.cache_data
def load_menu():
    if os.path.exists(MENU_FILE):
        return pd.read_csv(MENU_FILE)
    return pd.DataFrame(columns=["類別", "廠商", "品項"])

df_menu_raw = load_menu()

# --- 初始化 Session State ---
if 'page' not in st.session_state: st.session_state.page = "登記"
if 'step' not in st.session_state: st.session_state.step = 1

# --- 頁面導航 ---
col_nav1, col_nav2 = st.columns(2)
if col_nav1.button("📝 進入登記", use_container_width=True): 
    st.session_state.page = "登記"
    st.rerun()
if col_nav2.button("📊 查看紀錄", use_container_width=True): 
    st.session_state.page = "紀錄"
    st.rerun()

st.divider()

# --- A. 登記頁面 ---
if st.session_state.page == "登記":
    st.header("🍎 雲端報廢登記")
    
    if st.session_state.step == 1:
        st.subheader("1. 選擇商品類別")
        categories = df_menu_raw["類別"].unique()
        v_cols = st.columns(2)
        for i, cat_name in enumerate(categories):
            with v_cols[i % 2]:
                if st.button(cat_name, use_container_width=True):
                    st.session_state.selected_cat = cat_name
                    st.session_state.step = 2
                    st.rerun()

    elif st.session_state.step == 2:
        st.subheader(f"2. 選擇品項 ({st.session_state.selected_cat})")
        category_items = df_menu_raw[df_menu_raw["類別"] == st.session_state.selected_cat]
        i_cols = st.columns(2)
        for i, (idx, row) in enumerate(category_items.iterrows()):
            with i_cols[i % 2]:
                if st.button(row["品項"], use_container_width=True, key=f"item_{idx}"):
                    st.session_state.selected_item = row["品項"]
                    st.session_state.selected_vendor = row["廠商"]
                    st.session_state.step = 3
                    st.rerun()
        if st.button("⬅️ 返回重選類別", use_container_width=True):
            st.session_state.step = 1
            st.rerun()

    elif st.session_state.step == 3:
        st.info(f"📍 已選：{st.session_state.selected_item}")
        weight = st.number_input("3. 輸入重量 (克)", min_value=0, step=50, value=0)
        if st.button("確認重量，選擇原因 ➔", type="primary", use_container_width=True):
            st.session_state.temp_weight = weight
            st.session_state.step = 4
            st.rerun()

    elif st.session_state.step == 4:
        st.warning("最後一步：請選擇報廢原因")
        reasons = ["基本損耗", "客人退貨", "品質不佳", "掉落地面"]
        for reason in reasons:
            if st.button(reason, use_container_width=True):
                # 準備新資料
                new_data = pd.DataFrame([{
                    "輸入時間": get_taiwan_time().strftime("%Y-%m-%d %H:%M"),
                    "類別": st.session_state.selected_cat,
                    "廠商": st.session_state.selected_vendor,
                    "品項": st.session_state.selected_item,
                    "重量(g)": st.session_state.temp_weight,
                    "報廢原因": reason
                }])
                
                # 讀取現有雲端資料並合併
                existing_data = conn.read(spreadsheet=SHEET_URL, usecols=[0,1,2,3,4,5])
                updated_df = pd.concat([existing_data, new_data], ignore_index=True)
                
                # 寫回 Google Sheets
                conn.update(spreadsheet=SHEET_URL, data=updated_df)
                
                st.session_state.page = "紀錄" 
                st.session_state.step = 1
                st.rerun()

# --- B. 紀錄頁面 ---
elif st.session_state.page == "紀錄":
    st.header("📊 雲端即時紀錄")
    
    # 從雲端讀取資料
    try:
        history_df = conn.read(spreadsheet=SHEET_URL)
        if not history_df.empty:
            st.table(history_df.tail(5).iloc[::-1]) # 顯示最後五筆
            
            if st.button("➕ 繼續登記下一筆", type="primary", use_container_width=True):
                st.session_state.page = "登記"
                st.session_state.step = 1
                st.rerun()
                
            # 清除功能 (同樣設密碼)
            with st.expander("🛠️ 管理員功能"):
                pwd = st.text_input("管理密碼", type="password")
                if st.button("清空雲端資料表"):
                    if pwd == "85129111":
                        empty_df = pd.DataFrame(columns=["輸入時間", "類別", "廠商", "品項", "重量(g)", "報廢原因"])
                        conn.update(spreadsheet=SHEET_URL, data=empty_df)
                        st.success("雲端資料已清空")
                        st.rerun()
    except:
        st.error("無法連線至雲端硬碟，請檢查 SHEET_URL 或權限設定")
