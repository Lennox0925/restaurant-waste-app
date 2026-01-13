import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --- 1. 初始化與樣式 ---
DATA_FILE = 'waste_records.csv'
MENU_FILE = 'menu.csv'
# 請在此填入您的 Google Drive 資料夾 ID (網址最後一串字元)
FOLDER_ID = "1R0P9mtMEYA2UIADZuVDhaQshLubUETK3"

st.set_page_config(page_title="餐廳報廢系統 (雲端資料夾備份版)", layout="centered")
st.markdown("""
    <style>
    div.stButton > button { height: 3.5em; font-size: 1.1rem !important; margin-bottom: 10px; }
    .stNumberInput input { font-size: 1.5rem !important; height: 3em !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 核心函數 ---
def get_taiwan_time():
    return datetime.utcnow() + timedelta(hours=8)

def get_drive_service():
    # 直接讀取 Secrets 裡的連線資訊
    info = st.secrets["connections"]["gsheets"]
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def upload_to_drive_folder():
    service = get_drive_service()
    now_tw = get_taiwan_time()
    # 檔名範例: 2026-01-14_報廢紀錄.csv
    file_name = f"{now_tw.strftime('%Y-%m-%d')}_waste_backup.csv"
    
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'rb') as f:
            media = MediaIoBaseUpload(io.BytesIO(f.read()), mimetype='text/csv')
            file_metadata = {'name': file_name, 'parents': [FOLDER_ID]}
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            return file.get('id')
    return None

# 確保本地 CSV 存在
COLUMNS = ["輸入時間", "類別", "廠商", "品項", "重量(g)", "報廢原因"]
if not os.path.exists(DATA_FILE):
    pd.DataFrame(columns=COLUMNS).to_csv(DATA_FILE, index=False, encoding='utf-8-sig')

# --- 3. 讀取選單資料 ---
@st.cache_data
def load_menu():
    if os.path.exists(MENU_FILE):
        return pd.read_csv(MENU_FILE)
    return pd.DataFrame(columns=["類別", "廠商", "品項"])

df_menu_raw = load_menu()

# --- 4. Session State ---
if 'page' not in st.session_state: st.session_state.page = "登記"
if 'step' not in st.session_state: st.session_state.step = 1

# --- 5. 導航列 ---
col_nav1, col_nav2 = st.columns(2)
if col_nav1.button("📝 進入登記", use_container_width=True): 
    st.session_state.page = "登記"; st.session_state.step = 1; st.rerun()
if col_nav2.button("📊 查看紀錄", use_container_width=True): 
    st.session_state.page = "紀錄"; st.rerun()

st.divider()

# --- A. 登記頁面 ---
if st.session_state.page == "登記":
    st.header("🍎 報廢登記 (本地存檔)")
    
    if st.session_state.step == 1:
        st.subheader("1. 選擇商品類別")
        categories = df_menu_raw["類別"].unique()
        v_cols = st.columns(2)
        for i, cat_name in enumerate(categories):
            with v_cols[i % 2]:
                if st.button(cat_name, use_container_width=True):
                    st.session_state.selected_cat = cat_name
                    st.session_state.step = 2; st.rerun()

    elif st.session_state.step == 2:
        st.subheader(f"2. 選擇品項 ({st.session_state.selected_cat})")
        category_items = df_menu_raw[df_menu_raw["類別"] == st.session_state.selected_cat]
        i_cols = st.columns(2)
        for i, (idx, row) in enumerate(category_items.iterrows()):
            with i_cols[i % 2]:
                if st.button(row["品項"], use_container_width=True, key=f"item_{idx}"):
                    st.session_state.selected_item = row["品項"]
                    st.session_state.selected_vendor = row["廠商"]
                    st.session_state.step = 3; st.rerun()
        if st.button("⬅️ 返回重選類別", use_container_width=True):
            st.session_state.step = 1; st.rerun()

    elif st.session_state.step == 3:
        st.info(f"📍 已選：{st.session_state.selected_item}")
        weight = st.number_input("3. 輸入重量 (克)", min_value=0, step=50, value=0)
        if st.button("確認重量，選擇原因 ➔", type="primary", use_container_width=True):
            st.session_state.temp_weight = weight
            st.session_state.step = 4; st.rerun()

    elif st.session_state.step == 4:
        st.warning("最後一步：請選擇報廢原因")
        reasons = ["基本損耗", "客人退貨", "品質不佳", "掉落地面"]
        for reason in reasons:
            if st.button(reason, use_container_width=True):
                new_data = pd.DataFrame([{
                    "輸入時間": get_taiwan_time().strftime("%Y-%m-%d %H:%M"),
                    "類別": st.session_state.selected_cat,
                    "廠商": st.session_state.selected_vendor,
                    "品項": st.session_state.selected_item,
                    "重量(g)": st.session_state.temp_weight,
                    "報廢原因": reason
                }])
                df_local = pd.read_csv(DATA_FILE)
                pd.concat([df_local, new_data], ignore_index=True).to_csv(DATA_FILE, index=False, encoding='utf-8-sig')
                st.success("✅ 登記成功！")
                st.session_state.page = "紀錄"; st.session_state.step = 1; st.rerun()

# --- B. 紀錄頁面 ---
elif st.session_state.page == "紀錄":
    st.header("📊 當前本地紀錄")
    if os.path.exists(DATA_FILE):
        df_history = pd.read_csv(DATA_FILE)
        if not df_history.empty:
            st.table(df_history.tail(5).iloc[::-1])
            st.divider()
            
            # 雲端資料夾上傳按鈕
            st.subheader("📂 雲端備份管理")
            if st.button("🚀 將 CSV 檔案上傳至 Google Drive 資料夾", use_container_width=True):
                with st.spinner("檔案上傳中..."):
                    try:
                        file_id = upload_to_drive_folder()
                        st.success(f"✅ 上傳成功！檔案 ID: {file_id}")
                    except Exception as e:
                        st.error(f"❌ 上傳失敗：{e}")
            
            st.divider()
            with st.expander("🛠️ 進階管理 (清空本地資料)"):
                pwd = st.text_input("輸入 85129111 清除", type="password")
                if st.button("確認清除"):
                    if pwd == "85129111":
                        pd.DataFrame(columns=COLUMNS).to_csv(DATA_FILE, index=False, encoding='utf-8-sig')
                        st.success("已清除"); st.rerun()
        else:
            st.info("目前無資料")

