import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import io
import pickle
import base64
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --- 1. 初始化與設定 ---
st.set_page_config(page_title="餐廳報廢系統-2026雲端版", layout="centered")

if 'page' not in st.session_state:
    st.session_state.page = "登記"
if 'step' not in st.session_state:
    st.session_state.step = 1

# --- 核心邏輯：台灣時區與自動分月 ---
def get_taiwan_time():
    # 2026 台灣時區修正
    return datetime.utcnow() + timedelta(hours=8)

def get_current_month_file():
    """根據當前月份產生檔名，確保不同月份資料分開儲存"""
    now_tw = get_taiwan_time()
    return f"waste_{now_tw.strftime('%Y-%m')}.csv"

DATA_FILE = get_current_month_file()
MENU_FILE = 'menu.csv'
COLUMNS = ["輸入時間", "類別", "廠商", "品項", "重量(g)", "報廢原因"]

# 確保當月本地檔案存在
if not os.path.exists(DATA_FILE):
    pd.DataFrame(columns=COLUMNS).to_csv(DATA_FILE, index=False, encoding='utf-8-sig')

# [務必修改] 雲端硬碟資料夾 ID
FOLDER_ID = "1R0P9mtMEYA2UIADZuVDhaQshLubUETK3"

# CSS 樣式優化
st.markdown("""
    <style>
    div.stButton > button { height: 3.5em; font-size: 1.1rem !important; margin-bottom: 10px; border-radius: 8px; }
    .stNumberInput input { font-size: 1.5rem !important; height: 3em !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 核心功能函數 ---
def get_drive_service():
    creds = None
    try:
        auth_info = st.secrets.get("google_auth")
        if auth_info and "token_base64" in auth_info:
            token_data = base64.b64decode(auth_info["token_base64"])
            creds = pickle.loads(token_data)
    except Exception: pass 

    if not creds and os.path.exists('token.pickle'):
        try:
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        except Exception: pass

    if creds and creds.expired and creds.refresh_token:
        try: creds.refresh(Request())
        except Exception: return None
    
    if not creds or not creds.valid: return None
    return build('drive', 'v3', credentials=creds)

def upload_to_drive():
    service = get_drive_service()
    if not service: return None
    now_tw = get_taiwan_time()
    # 雲端備份檔名包含當月資訊
    file_name = f"{now_tw.strftime('%Y-%m-%d_%H%M')}_backup_{DATA_FILE}"
    try:
        with open(DATA_FILE, 'rb') as f:
            media = MediaIoBaseUpload(io.BytesIO(f.read()), mimetype='text/csv')
            file_metadata = {'name': file_name, 'parents': [FOLDER_ID]}
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e:
        st.error(f"上傳至雲端失敗: {e}")
        return None

@st.cache_data
def load_menu():
    if os.path.exists(MENU_FILE):
        return pd.read_csv(MENU_FILE)
    return pd.DataFrame(columns=["類別", "廠商", "品項"])

df_menu_raw = load_menu()

# --- 3. 頁面導航 ---
c1, c2 = st.columns(2)
if c1.button("📝 報廢登記", use_container_width=True): 
    st.session_state.page = "登記"; st.session_state.step = 1; st.rerun()
if c2.button("📊 紀錄查看", use_container_width=True): 
    st.session_state.page = "紀錄"; st.rerun()

st.divider()

# --- 4. 登記頁面邏輯 ---
if st.session_state.page == "登記":
    st.header(f"🍎 報廢登記 ({get_taiwan_time().strftime('%Y-%m')})")
    if st.session_state.step == 1:
        st.subheader("1. 選擇類別")
        cats = df_menu_raw["類別"].unique()
        if len(cats) == 0: st.warning("請準備 menu.csv")
        else:
            v_cols = st.columns(2)
            for i, c_name in enumerate(cats):
                with v_cols[i % 2]:
                    if st.button(c_name, use_container_width=True):
                        st.session_state.selected_cat = c_name
                        st.session_state.step = 2; st.rerun()

    elif st.session_state.step == 2:
        st.subheader(f"2. 選擇品項 ({st.session_state.selected_cat})")
        items = df_menu_raw[df_menu_raw["類別"] == st.session_state.selected_cat]
        i_cols = st.columns(2)
        for i, (idx, row) in enumerate(items.iterrows()):
            with i_cols[i % 2]:
                if st.button(row["品項"], use_container_width=True, key=f"it_{idx}"):
                    st.session_state.selected_item = row["品項"]
                    st.session_state.selected_vendor = row["廠商"]
                    st.session_state.step = 3; st.rerun()
        if st.button("⬅️ 返回"): st.session_state.step = 1; st.rerun()

    elif st.session_state.step == 3:
        st.info(f"📍 品項：{st.session_state.selected_item}")
        weight = st.number_input("3. 輸入重量 (g)", min_value="", step=50)
        if st.button("下一步：選擇原因 ➔", use_container_width=True, type="primary"):
            st.session_state.temp_weight = weight
            st.session_state.step = 4; st.rerun()

    elif st.session_state.step == 4:
        st.warning("最後一步：請選擇原因")
        for r in ["正常損耗", "客人退貨", "品質不佳", "掉落地面"]:
            if st.button(r, use_container_width=True):
                new_row = pd.DataFrame([{
                    "輸入時間": get_taiwan_time().strftime("%Y-%m-%d %H:%M"),
                    "類別": st.session_state.selected_cat,
                    "廠商": st.session_state.selected_vendor,
                    "品項": st.session_state.selected_item,
                    "重量(g)": st.session_state.temp_weight,
                    "報廢原因": r
                }])
                df_local = pd.read_csv(DATA_FILE)
                pd.concat([df_local, new_row], ignore_index=True).to_csv(DATA_FILE, index=False, encoding='utf-8-sig')
                st.session_state.page = "紀錄"; st.rerun()

# --- 5. 紀錄頁面邏輯 ---
elif st.session_state.page == "紀錄":
    st.header(f"📊 {get_taiwan_time().strftime('%Y-%m')} 紀錄")
    
    # 顯示刪除成功提示 (若存在)
    if 'delete_msg' in st.session_state:
        st.success(st.session_state.delete_msg)
        del st.session_state.delete_msg

    if os.path.exists(DATA_FILE):
        df_h = pd.read_csv(DATA_FILE)
        if not df_h.empty:
            # 顯示最近 5 筆紀錄 (倒序)
            st.table(df_h.tail(5).iloc[::-1])
            
            # --- 刪除最後一筆功能 ---
            with st.popover("🗑️ 刪除最新一筆資料", use_container_width=True):
                last_item = df_h.iloc[-1]
                st.warning("確定要刪除此筆資料嗎？")
                st.write(f"**品項：** {last_item['品項']} ({last_item['重量(g)']}g)")
                st.write(f"**時間：** {last_item['輸入時間']}")
                
                if st.button("確認刪除並回歷史紀錄頁面", type="primary", use_container_width=True):
                    # 執行刪除
                    df_h = df_h.drop(df_h.index[-1])
                    df_h.to_csv(DATA_FILE, index=False, encoding='utf-8-sig')
                    # 設定提示文字並刷新，刷新後 Popover 會自動關閉
                    st.session_state.delete_msg = f"✅ 已刪除：{last_item['品項']}"
                    st.rerun()
            
            st.divider()
            st.subheader("📂 雲端管理")
            if st.button("🚀 備份本月資料到雲端", use_container_width=True, type="primary"):
                with st.spinner("雲端傳輸中..."):
                    fid = upload_to_drive()
                    if fid: st.success(f"✅ 備份成功！檔案 ID: {fid}")
            
            with st.expander("🛠️ 管理員功能(清空內容)"):
                if st.text_input("管理密碼", type="password") == "85129111":
                    if st.button("清空本月本地資料"):
                        pd.DataFrame(columns=COLUMNS).to_csv(DATA_FILE, index=False, encoding='utf-8-sig')
                        st.success("資料已清空"); st.rerun()
        else:
            st.info("本月目前尚無資料")

