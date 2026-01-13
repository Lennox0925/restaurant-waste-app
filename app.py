import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --- 1. 設定區域 ---
DATA_FILE = 'waste_records.csv'
MENU_FILE = 'menu.csv'
COLUMNS = ["輸入時間", "類別", "廠商", "品項", "重量(g)", "報廢原因"]

# [請修改此處] 填入您已授權給服務帳戶的「個人雲端硬碟資料夾 ID」
FOLDER_ID = "1R0P9mtMEYA2UIADZuVDhaQshLubUETK3"

st.set_page_config(page_title="餐廳報廢系統-2026雲端版", layout="centered")

# CSS 樣式優化
st.markdown("""
    <style>
    div.stButton > button { height: 3.5em; font-size: 1.1rem !important; margin-bottom: 10px; }
    .stNumberInput input { font-size: 1.5rem !important; height: 3em !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 核心功能函數 ---
def get_taiwan_time():
    # 2026 年時區修正 (UTC+8)
    return datetime.utcnow() + timedelta(hours=8)

def get_drive_service():
    # 從 Streamlit Secrets 讀取服務帳戶資訊
    try:
        info = st.secrets["connections"]["gsheets"]
        creds = service_account.Credentials.from_service_account_info(info)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"認證失敗，請檢查 Secrets 設定: {e}")
        return None

def upload_to_personal_drive():
    """上傳檔案至指定的個人雲端資料夾，避開服務帳戶 0 配額限制"""
    service = get_drive_service()
    if not service: return None
    
    now_tw = get_taiwan_time()
    file_name = f"{now_tw.strftime('%Y-%m-%d_%H%M')}_waste_backup.csv"
    
    if not os.path.exists(DATA_FILE):
        st.error("找不到本地 CSV 檔案")
        return None

    try:
        with open(DATA_FILE, 'rb') as f:
            media = MediaIoBaseUpload(io.BytesIO(f.read()), mimetype='text/csv')
            file_metadata = {
                'name': file_name,
                'parents': [FOLDER_ID]
            }
            
            # 重要：supportsAllDrives=True 確保能寫入非服務帳戶自有的空間
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id',
                supportsAllDrives=True 
            ).execute()
            
        return file.get('id')
    except Exception as e:
        st.error(f"Drive API 執行錯誤: {e}")
        return None

# 初始化本地 CSV
if not os.path.exists(DATA_FILE):
    pd.DataFrame(columns=COLUMNS).to_csv(DATA_FILE, index=False, encoding='utf-8-sig')

# --- 3. 讀取選單 ---
@st.cache_data
def load_menu():
    if os.path.exists(MENU_FILE):
        return pd.read_csv(MENU_FILE)
    return pd.DataFrame(columns=["類別", "廠商", "品項"])

df_menu_raw = load_menu()

# --- 4. Session State ---
if 'page' not in st.session_state: st.session_state.page = "登記"
if 'step' not in st.session_state: st.session_state.step = 1

# --- 5. 頁面導航 ---
c1, c2 = st.columns(2)
if c1.button("📝 進入登記", use_container_width=True): 
    st.session_state.page = "登記"; st.session_state.step = 1; st.rerun()
if c2.button("📊 查看紀錄", use_container_width=True): 
    st.session_state.page = "紀錄"; st.rerun()

st.divider()

# --- A. 登記頁面 ---
if st.session_state.page == "登記":
    st.header("🍎 報廢登記")
    
    if st.session_state.step == 1:
        st.subheader("1. 選擇商品類別")
        cats = df_menu_raw["類別"].unique()
        if len(cats) == 0:
            st.warning("請先準備 menu.csv 檔案")
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
        if st.button("⬅️ 返回", use_container_width=True):
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
        for r in reasons:
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
                st.success("✅ 登記完成")
                st.session_state.page = "紀錄"; st.session_state.step = 1; st.rerun()

# --- B. 紀錄頁面 ---
elif st.session_state.page == "紀錄":
    st.header("📊 當前本地紀錄")
    if os.path.exists(DATA_FILE):
        df_h = pd.read_csv(DATA_FILE)
        if not df_h.empty:
            st.table(df_h.tail(5).iloc[::-1])
            st.divider()
            
            st.subheader("📂 雲端備份管理")
            if st.button("🚀 備份 CSV 至個人 Google Drive", use_container_width=True):
                with st.spinner("檔案傳輸中..."):
                    fid = upload_to_personal_drive()
                    if fid:
                        st.success(f"✅ 上傳成功！檔案 ID: {fid}")
            
            st.divider()
            with st.expander("🛠️ 進階管理 (清空本地)"):
                pwd = st.text_input("輸入管理密碼", type="password")
                if st.button("確認清除"):
                    if pwd == "85129111":
                        pd.DataFrame(columns=COLUMNS).to_csv(DATA_FILE, index=False, encoding='utf-8-sig')
                        st.success("資料已清空"); st.rerun()
                    else:
                        st.error("密碼錯誤")
        else:
            st.info("目前無資料")
