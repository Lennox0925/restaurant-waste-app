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

# [請修改此處] 填入目標 Google Drive 資料夾 ID
FOLDER_ID = "1R0P9mtMEYA2UIADZuVDhaQshLubUETK3"
# [請修改此處] 填入您的個人 Gmail，用於接收檔案擁有權 (解決 403 空間不足問題)
YOUR_GMAIL = "likegb1018@gmail.com"

st.set_page_config(page_title="餐廳報廢系統-雲端備份版", layout="centered")

# CSS 樣式優化
st.markdown("""
    <style>
    div.stButton > button { height: 3.5em; font-size: 1.1rem !important; margin-bottom: 10px; }
    .stNumberInput input { font-size: 1.5rem !important; height: 3em !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 核心功能函數 ---
def get_taiwan_time():
    # 2026 年時區修正
    return datetime.utcnow() + timedelta(hours=8)

def get_drive_service():
    # 讀取 Secrets 中的金鑰
    info = st.secrets["connections"]["gsheets"]
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def upload_and_transfer_ownership():
    """上傳檔案並立即轉移擁有權給個人帳號，以解決 403 空間配額問題"""
    service = get_drive_service()
    now_tw = get_taiwan_time()
    file_name = f"{now_tw.strftime('%Y-%m-%d')}_waste_backup.csv"
    
    if not os.path.exists(DATA_FILE):
        return None

    # A. 讀取並上傳檔案
    with open(DATA_FILE, 'rb') as f:
        media = MediaIoBaseUpload(io.BytesIO(f.read()), mimetype='text/csv')
        file_metadata = {
            'name': file_name,
            'parents': [FOLDER_ID]
        }
        
        # 建立檔案
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()
        
        file_id = file.get('id')

    # B. 關鍵動作：將擁有權轉移給個人 Gmail
    try:
        new_permission = {
            'type': 'user',
            'role': 'owner',
            'emailAddress': YOUR_GMAIL
        }
        
        # 執行權限變更 (transferOwnership=True 才能解決空間問題)
        service.permissions().create(
            fileId=file_id,
            body=new_permission,
            transferOwnership=True,
            supportsAllDrives=True
        ).execute()
    except Exception as e:
        # 若轉移失敗，至少檔案已上傳(但可能佔用服務帳戶那極小的暫存空間)
        st.warning(f"檔案已上傳但擁有權轉移失敗: {e}")

    return file_id

# 確保本地 CSV 初始化
COLUMNS = ["輸入時間", "類別", "廠商", "品項", "重量(g)", "報廢原因"]
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
    st.header("🍎 報廢登記 (本地存檔)")
    
    if st.session_state.step == 1:
        st.subheader("1. 選擇商品類別")
        cats = df_menu_raw["類別"].unique()
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
            
            # 備份功能
            st.subheader("📂 雲端備份管理")
            if st.button("🚀 備份 CSV 至 Google Drive 資料夾", use_container_width=True):
                with st.spinner("檔案傳輸中..."):
                    try:
                        fid = upload_and_transfer_ownership()
                        st.success(f"✅ 上傳成功！並已轉移擁有權。檔案 ID: {fid}")
                    except Exception as e:
                        st.error(f"❌ 備份失敗：{e}")
            
            st.divider()
            with st.expander("🛠️ 進階管理 (清空本地)"):
                pwd = st.text_input("輸入密碼 85129111", type="password")
                if st.button("確認清除"):
                    if pwd == "85129111":
                        pd.DataFrame(columns=COLUMNS).to_csv(DATA_FILE, index=False, encoding='utf-8-sig')
                        st.success("資料已清空"); st.rerun()
        else:
            st.info("目前無資料")
