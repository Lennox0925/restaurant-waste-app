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

# 務必先初始化 Session State，避免讀取錯誤
if 'page' not in st.session_state:
    st.session_state.page = "登記"
if 'step' not in st.session_state:
    st.session_state.step = 1

DATA_FILE = 'waste_records.csv'
MENU_FILE = 'menu.csv'
COLUMNS = ["輸入時間", "類別", "廠商", "品項", "重量(g)", "報廢原因"]

# [務必修改] 填入您個人雲端硬碟的資料夾 ID
FOLDER_ID = "1R0P9mtMEYA2UIADZuVDhaQshLubUETK3"

# 權限範圍必須與產生 token.pickle 時一致
SCOPES = ['www.googleapis.com']

# CSS 樣式優化
st.markdown("""
    <style>
    div.stButton > button { height: 3.5em; font-size: 1.1rem !important; margin-bottom: 10px; border-radius: 8px; }
    .stNumberInput input { font-size: 1.5rem !important; height: 3em !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 核心功能函數 ---
def get_taiwan_time():
    # 2026 台灣時區修正
    return datetime.utcnow() + timedelta(hours=8)

def get_drive_service():
    """安全授權邏輯：支援 Secrets 與本地 token.pickle"""
    creds = None
    
    # 方式 A: 安全嘗試從 Secrets 讀取 (不直接存取鍵值以防噴錯)
    try:
        # 使用 .get 避免 'st.secrets has no key "connections"' 報錯
        auth_info = st.secrets.get("google_auth")
        if auth_info and "token_base64" in auth_info:
            token_data = base64.b64decode(auth_info["token_base64"])
            creds = pickle.loads(token_data)
    except Exception:
        pass 

    # 方式 B: 從本地檔案讀取 (token.pickle)
    if not creds and os.path.exists('token.pickle'):
        try:
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        except Exception as e:
            st.error(f"讀取 token.pickle 失敗: {e}")

    # 驗證憑證有效性
    if creds:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                st.error(f"憑證過期且刷新失敗: {e}")
                return None
    
    if not creds or not creds.valid:
        st.error("⚠️ 認證失敗：找不到有效的授權憑證。")
        st.info("請確保環境中有 token.pickle 檔案，或在 Secrets 中設定 google_auth。")
        return None

    return build('drive', 'v3', credentials=creds)

def upload_to_drive():
    service = get_drive_service()
    if not service: return None
    
    now_tw = get_taiwan_time()
    file_name = f"{now_tw.strftime('%Y-%m-%d_%H%M')}_waste_backup.csv"
    
    try:
        with open(DATA_FILE, 'rb') as f:
            media = MediaIoBaseUpload(io.BytesIO(f.read()), mimetype='text/csv')
            file_metadata = {
                'name': file_name,
                'parents': [FOLDER_ID]
            }
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
        return file.get('id')
    except Exception as e:
        st.error(f"上傳至雲端失敗: {e}")
        return None

# 初始化本地紀錄
if not os.path.exists(DATA_FILE):
    pd.DataFrame(columns=COLUMNS).to_csv(DATA_FILE, index=False, encoding='utf-8-sig')

# 讀取選單
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
    st.header("🍎 報廢登記")
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
        weight = st.number_input("3. 輸入重量 (g)", min_value=0, step=50)
        if st.button("下一步：選擇原因 ➔", use_container_width=True, type="primary"):
            st.session_state.temp_weight = weight
            st.session_state.step = 4; st.rerun()

    elif st.session_state.step == 4:
        st.warning("最後一步：請選擇原因")
        for r in ["基本損耗", "客人退貨", "品質不佳", "掉落地面"]:
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
                st.success("✅ 登記成功"); st.session_state.page = "紀錄"; st.rerun()

# --- 5. 紀錄頁面邏輯 ---
elif st.session_state.page == "紀錄":
    st.header("📊 本地歷史紀錄")
    if os.path.exists(DATA_FILE):
        df_h = pd.read_csv(DATA_FILE)
        if not df_h.empty:
            st.table(df_h.tail(5).iloc[::-1])
            st.divider()
            st.subheader("📂 雲端管理")
            if st.button("🚀 執行自動雲端備份", use_container_width=True, type="primary"):
                with st.spinner("傳輸中..."):
                    fid = upload_to_drive()
                    if fid: st.success(f"✅ 備份成功！檔案 ID: {fid}")
            
            with st.expander("🛠️ 管理員功能"):
                if st.text_input("密碼", type="password") == "85129111":
                    if st.button("清空所有本地資料"):
                        pd.DataFrame(columns=COLUMNS).to_csv(DATA_FILE, index=False, encoding='utf-8-sig')
                        st.success("資料已清空"); st.rerun()
        else:
            st.info("目前尚無資料")
