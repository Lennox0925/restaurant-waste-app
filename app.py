import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import os

# --- 1. 設定頁面與樣式 ---
st.set_page_config(page_title="餐廳報廢系統 (雲端分月版)", layout="centered")

# 請將下方網址替換為您的 Google 試算表網址
# 務必開啟試算表權限為「知道連結的任何人」皆可「編輯」
SHEET_URL = "docs.google.com/spreadsheets/d/1FOInPuBU3yZpfM3ohS0HHOM2App2p2UwaoEbHMFv6wM/edit"

# 建立 Google Sheets 連線
conn = st.connection("gsheets", type=GSheetsConnection)

def get_taiwan_time():
    # 2026 年 Streamlit Cloud 環境 (UTC+8 修正)
    return datetime.utcnow() + timedelta(hours=8)

# --- 2. 讀取選單資料 (menu.csv) ---
MENU_FILE = 'menu.csv'
@st.cache_data
def load_menu():
    if os.path.exists(MENU_FILE):
        return pd.read_csv(MENU_FILE)
    return pd.DataFrame(columns=["類別", "廠商", "品項"])

df_menu_raw = load_menu()

# --- 3. 初始化 Session State ---
if 'page' not in st.session_state: st.session_state.page = "登記"
if 'step' not in st.session_state: st.session_state.step = 1

# --- 4. 頁面導航按鈕 ---
col_nav1, col_nav2 = st.columns(2)
if col_nav1.button("📝 進入登記", use_container_width=True): 
    st.session_state.page = "登記"
    st.session_state.step = 1
    st.rerun()
if col_nav2.button("📊 查看紀錄", use_container_width=True): 
    st.session_state.page = "紀錄"
    st.rerun()

st.divider()

# --- A. 登記頁面邏輯 ---
if st.session_state.page == "登記":
    st.header("🍎 雲端報廢登記")
    
    # 步驟 1: 選擇商品類別
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

    # 步驟 2: 選擇品項
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

    # 步驟 3: 輸入重量
    elif st.session_state.step == 3:
        st.info(f"📍 已選：{st.session_state.selected_cat} > {st.session_state.selected_item}")
        weight = st.number_input("3. 輸入重量 (克)", min_value=0, step=50, value=0)
        if st.button("確認重量，選擇原因 ➔", type="primary", use_container_width=True):
            st.session_state.temp_weight = weight
            st.session_state.step = 4
            st.rerun()

    # 步驟 4: 選擇報廢原因並儲存
    elif st.session_state.step == 4:
        st.warning("最後一步：請選擇報廢原因")
        reasons = ["基本損耗", "客人退貨", "品質不佳", "掉落地面"]
        for reason in reasons:
            if st.button(reason, use_container_width=True):
                now_tw = get_taiwan_time()
                # 分頁名稱設定為當前年月 (例如: 2026-01)
                month_sheet_name = now_tw.strftime("%Y-%m")
                
                new_data = pd.DataFrame([{
                    "輸入時間": now_tw.strftime("%Y-%m-%d %H:%M"),
                    "類別": st.session_state.selected_cat,
                    "廠商": st.session_state.selected_vendor,
                    "品項": st.session_state.selected_item,
                    "重量(g)": st.session_state.temp_weight,
                    "報廢原因": reason
                }])
                
                # 建立連線 (它會自動去 Secrets 讀取設定)
                conn = st.connection("gsheets", type=GSheetsConnection)

                # --- 在登記儲存時 ---
                try:
                    # 僅指定 worksheet 名稱，不要傳入 spreadsheet=SHEET_URL
                    existing_data = conn.read(worksheet=month_sheet_name, ttl=0)
                    updated_df = pd.concat([existing_data, new_data], ignore_index=True)
                except Exception:
                    # 如果找不到分頁，視為新分頁
                    updated_df = new_data

                # 更新雲端資料
                conn.update(worksheet=month_sheet_name, data=updated_df)

                # --- 在查看紀錄時 ---
                history_df = conn.read(worksheet=month_sheet_name, ttl=0)


# --- B. 紀錄頁面邏輯 ---
elif st.session_state.page == "紀錄":
    now_tw = get_taiwan_time()
    month_sheet_name = now_tw.strftime("%Y-%m")
    st.header(f"📊 {month_sheet_name} 雲端紀錄")
    
    try:
        # 指定讀取當月的工作表
        history_df = conn.read(spreadsheet=SHEET_URL, worksheet=month_sheet_name)
        if not history_df.empty:
            # 顯示最新 5 筆紀錄
            st.table(history_df.tail(5).iloc[::-1])
            
            st.divider()
            if st.button("➕ 繼續登記下一筆", type="primary", use_container_width=True):
                st.session_state.page = "登記"
                st.session_state.step = 1
                st.rerun()
            
            # 管理員清除當月資料
            with st.expander("🛠️ 管理員功能"):
                pwd = st.text_input("管理密碼", type="password")
                if st.button(f"清空 {month_sheet_name} 資料表"):
                    if pwd == "85129111":
                        empty_df = pd.DataFrame(columns=["輸入時間", "類別", "廠商", "品項", "重量(g)", "報廢原因"])
                        conn.update(spreadsheet=SHEET_URL, worksheet=month_sheet_name, data=empty_df)
                        st.success(f"{month_sheet_name} 資料已清空")
                        st.rerun()
                    else:
                        st.error("密碼錯誤")
        else:
            st.info(f"{month_sheet_name} 目前尚無資料")
    except Exception:
        st.warning(f"尚未建立 {month_sheet_name} 工作表，請先完成第一次登記。")







