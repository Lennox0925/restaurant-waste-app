
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

# [請修改此處] 填入您已授權給服務帳戶的「個人雲端硬碟資料夾 ID」
FOLDER_ID = "1R0P9mtMEYA2UIADZuVDhaQshLubUETK3"

st.set_page_config(page_title="餐廳報廢系統-個人雲端版", layout="centered")

# --- 2. 核心功能函數 ---
def get_taiwan_time():
    return datetime.utcnow() + timedelta(hours=8)

def get_drive_service():
    info = st.secrets["connections"]["gsheets"]
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def upload_to_personal_drive():
    """直接上傳至已授權的個人資料夾，使用個人帳號的配額"""
    service = get_drive_service()
    now_tw = get_taiwan_time()
    file_name = f"{now_tw.strftime('%Y-%m-%d')}_waste_backup.csv"
    
    if not os.path.exists(DATA_FILE):
        return None

    with open(DATA_FILE, 'rb') as f:
        media = MediaIoBaseUpload(io.BytesIO(f.read()), mimetype='text/csv')
        file_metadata = {
            'name': file_name,
            'parents': [FOLDER_ID] # 指定存入個人擁有的資料夾
        }
        
        # 建立檔案。雖然是由服務帳戶建立，但存放在個人資料夾時會消耗該資料夾擁有者的空間
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True # 必須開啟以支援存取非服務帳戶自有的空間
        ).execute()
        
    return file.get('id')

# (其餘資料處理與 UI 邏輯保持不變...)
# ... [省略中間 UI 程式碼] ...

# --- B. 紀錄頁面備份按鈕部分 ---
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
                    try:
                        fid = upload_to_personal_drive()
                        st.success(f"✅ 上傳成功！檔案已存入您的個人雲端資料夾。ID: {fid}")
                    except Exception as e:
                        st.error(f"❌ 備份失敗：{e}")
                        st.info("請檢查：1. 資料夾 ID 是否正確 2. 是否已將服務帳戶設為資料夾編輯者")
