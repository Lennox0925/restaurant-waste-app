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
st.set_page_config(page_title="餐廳報廢系統-雲端部署版", layout="centered")

if 'page' not in st.session_state:
    st.session_state.page = "登記"
if 'step' not in st.session_state:
    st.session_state.step = 1

DATA_FILE = 'waste_records.csv'
MENU_FILE = 'menu.csv'
COLUMNS = ["輸入時間", "類別", "廠商", "品項", "重量(g)", "報廢原因"]

# [務必修改] 填入您個人雲端硬碟的資料夾 ID
FOLDER_ID = "1R0P9mtMEYA2UIADZuVDhaQshLubUETK3"

# --- 新增權限範圍定義 ---
# 使用 drive.file 是最安全的作法，代表程式只能存取由它自己建立的檔案
SCOPES = ['https://www.googleapis.com/auth/drive.file'] 

# --- 2. 核心功能函數 ---
def get_taiwan_time():
    return datetime.utcnow() + timedelta(hours=8)

def get_drive_service():
    """專為雲端環境設計的授權邏輯"""
    creds = None
    
    # 方式 A: 從 Streamlit Secrets 讀取 (安全性高)
    if "google_auth" in st.secrets:
        try:
            token_data = base64.b64decode(st.secrets["google_auth"]["token_base64"])
            creds = pickle.loads(token_data)
        except Exception as e:
            st.error(f"Secrets Token 解析失敗: {e}")

    # 方式 B: 從本地檔案讀取 (方便部署)
    elif os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # 檢查憑證有效性並自動刷次
    if creds:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # 刷新後建議存回 session 或檔案，這裡簡化為直接使用
            except Exception as e:
                st.error(f"憑證刷新失敗: {e}")
                return None
    
    if not creds or not creds.valid:
        st.error("⚠️ 雲端授權失效！請在本地重新執行產生 token.pickle 並部署。")
        st.info("雲端環境不支援直接登入，請先在本地運行取得授權檔。")
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
            # 以個人身分執行，使用個人 15GB 配額
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
        return file.get('id')
    except Exception as e:
        st.error(f"上傳錯誤: {e}")
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
if c1.button("📝 進入登記", use_container_width=True): 
    st.session_state.page = "登記"; st.session_state.step = 1; st.rerun()
if c2.button("📊 查看紀錄", use_container_width=True): 
    st.session_state.page = "紀錄"; st.rerun()

st.divider()

# --- 4. 登記與紀錄頁面邏輯 (縮排修正) ---
if st.session_state.page == "登記":
    st.header("🍎 報廢登記")
    if st.session_state.step == 1:
        st.subheader("1. 選擇商品類別")
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
        st.info(f"📍 已選：{st.session_state.selected_item}")
        weight = st.number_input("3. 輸入重量 (克)", min_value=0, step=50)
        if st.button("確認重量 ➔"):
            st.session_state.temp_weight = weight
            st.session_state.step = 4; st.rerun()

    elif st.session_state.step == 4:
        st.warning("選擇原因")
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
                st.success("✅ 登記完成"); st.session_state.page = "紀錄"; st.rerun()

elif st.session_state.page == "紀錄":
    st.header("📊 當前本地紀錄")
    if os.path.exists(DATA_FILE):
        df_h = pd.read_csv(DATA_FILE)
        if not df_h.empty:
            st.table(df_h.tail(5).iloc[::-1])
            st.divider()
            st.subheader("📂 雲端備份")
            if st.button("🚀 執行自動雲端備份", use_container_width=True):
                with st.spinner("雲端傳輸中..."):
                    fid = upload_to_drive()
                    if fid: st.success(f"✅ 備份成功！ID: {fid}")
            
            with st.expander("🛠️ 清空本地"):
                if st.text_input("密碼", type="password") == "85129111":
                    if st.button("確認刪除"):
                        pd.DataFrame(columns=COLUMNS).to_csv(DATA_FILE, index=False, encoding='utf-8-sig')
                        st.rerun()
