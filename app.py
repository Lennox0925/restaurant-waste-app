import streamlit as st
import pandas as pd
import os
from datetime import datetime
from openpyxl import load_workbook
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
import base64
import requests
import pytz
from datetime import datetime, timezone, timedelta
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials

# 設定台灣時區
tw_timezone = pytz.timezone('Asia/Taipei')
now_taiwan = datetime.now(tw_timezone)

def sync_to_cloud(file_path, file_name):
    # 修改為您剛剛得到的 GAS 網址
    gas_url = "https://script.google.com/macros/s/AKfycbzl--f-A6aPraUel1_K8tP7NKueUo3eA0JYhVrXYg156yHCaeuWwzkDnbi_Exog_tEwCQ/exec" 
    
    with open(file_path, "rb") as f:
        encoded_string = base64.b64encode(f.read()).decode("utf-8")
        
    payload = {
        "fileName": file_name,
        "base64Data": encoded_string
    }
    
    try:
        response = requests.post(gas_url, json=payload)
        return response.text
    except:
        return "Failed"


# --- 1. 頁面基本配置 ---
st.set_page_config(page_title="餐廳崗位考核系統", layout="centered")

# --- 新增：Google Drive 上傳函數 ---
def upload_to_gdrive(file_path, file_name):
    SCOPES = ['https://www.googleapis.com']
    SERVICE_ACCOUNT_FILE = 'gdrive_auth.json' # 你的憑證檔案
    FOLDER_ID = '1Sgly7h0dw-5KwlczlBPwJmEAXMcZ0s4i' # 從網址列取得：://drive.google.com

    creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)

    file_metadata = {
        'name': file_name,
        'parents': [FOLDER_ID]
    }
    media = MediaFileUpload(file_path, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    
    # 檢查是否已有同名檔案，有的話更新，沒有的話上傳
    query = f"name = '{file_name}' and '{FOLDER_ID}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get('files', [])

    if files:
        file_id = files[0]['id']
        service.files().update(fileId=file_id, media_body=media).execute()
    else:
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()



# --- 2. 歷史紀錄總表維護邏輯 ---
# Google Drive 設定
FILE_NAME = "history_log.csv"

def get_gdrive_client():
    scope = ['https://www.googleapis.com']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gdrive"], scope)
    gauth = GoogleAuth()
    gauth.credentials = creds
    return GoogleDrive(gauth)

def save_summary_to_history(trainer, staff, staff_type, pos):
    drive = get_gdrive_client()
    
    # 尋找雲端硬碟中的檔案
    file_list = drive.ListFile({'q': f"title = '{FILE_NAME}' and trashed = false"}).GetList()
    gfile = file_list[0] if file_list else drive.CreateFile({'title': FILE_NAME})

    # 讀取現有資料或建立新的 DataFrame
    if file_list:
        content = gfile.GetContentString(encoding='utf-8-sig')
        df = pd.read_csv(io.StringIO(content))
    else:
        df = pd.DataFrame(columns=["時間", "訓練員", "受測人", "職位", "崗位"])

    # 新增資料
    tz_taiwan = timezone(timedelta(hours=8))
    now = datetime.now(tz_taiwan).strftime("%Y-%m-%d %H:%M")
    new_entry = pd.DataFrame([{
        "時間": now, 
        "訓練員": trainer, 
        "受測人": staff, 
        "職位": staff_type, 
        "崗位": pos
    }])
    df = pd.concat([df, new_entry], ignore_index=True)

    # 寫回雲端硬碟
    output = io.StringIO()
    df.to_csv(output, index=False, encoding='utf-8-sig')
    gfile.SetContentString(output.getvalue())
    gfile.Upload()
    
# --- 3. 資料讀取與架構初始化 ---
@st.cache_data
def load_app_data():
    if not os.path.exists('staff.csv'):
        st.error("找不到 staff.csv。")
        st.stop()
    
    staff_df = pd.read_csv('staff.csv', encoding='utf-8-sig')
    staff_df.columns = staff_df.columns.str.strip()
    
    if os.path.exists('standards.csv'):
        std_df = pd.read_csv('standards.csv', encoding='utf-8-sig')
        std_df.columns = std_df.columns.str.strip()
    else:
        std_df = pd.DataFrame(columns=['崗位時段', '崗位區域'])

    assessment_dir = "Assessment"
    if not os.path.exists(assessment_dir):
        os.makedirs(assessment_dir)
    
    all_files = [f for f in os.listdir(assessment_dir) if f.endswith('_考核內容.csv')]
    structure = []
    for file in all_files:
        try:
            clean_name = file.replace("_考核內容.csv", "")
            parts = clean_name.split("_")
            if len(parts) >= 2:
                structure.append({"時段": parts[0], "區域": parts[1], "檔名": file})
        except: continue
        
    return staff_df, pd.DataFrame(structure), std_df

staff_df, struct_df, standards_df = load_app_data()

# --- 4. CSS 樣式控制 ---
st.markdown("""
    <style>
    /* 保持原有的 Streamlit 佈局和按鈕樣式 */
    .main .block-container { max-width: 500px !important; margin: auto; padding-top: 2rem; display: flex; flex-direction: column; align-items: center; }
    [data-testid="stVerticalBlock"] > div { width: 100%; display: flex; flex-direction: column; align-items: center; }
    div.stButton { width: 100%; display: flex; justify-content: center; }
    div.stButton > button { width: 100% !important; max-width: 480px; height: 75px !important; font-size: 22px !important; margin-bottom: 16px; border-radius: 20px; border: none !important; background-color: #D8D8EB !important; color: #000000 !important; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    div.stButton > button p { font-weight: 400 !important; color: #000000 !important; }
    div.stButton > button:has(p:contains("正職人員")) { background-color: #BDE0FE !important; } 
    div.stButton > button:has(p:contains("兼職人員")) { background-color: #FFC8DD !important; }
    div.stButton > button:has(p:contains("📜")), div.stButton > button:has(p:contains("⬅️")), div.stButton > button:has(p:contains("👥")) { background-color: #FF5809 !important; height: 60px !important; }
    div.stButton > button:has(p:contains("✅")) { background-color: #FFADAD !important; }
    div.stButton > button:has(p:contains("🏠")) { background-color: #FDFFB6 !important; }
    
    /* 確保考核內容標籤放大 */
    .pos-container { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-bottom: 20px; width: 100%; }
    .pos-tag { 
        padding: 12px 20px !important; 
        border-radius: 15px !important; 
        font-size: 20px !important; /* 從 13px 放大至 20px */
        background-color: #F0F2F6; 
        border: 2px solid #DDD; 
        color: #555; 
        line-height: 1.5 !important;
    }
    .pos-tag-yes { border: 3px solid #9ACD32 !important; font-weight: bold !important; color: #000 !important; } 
    .pos-tag-no { border: 3px solid #FF0000 !important; font-weight: bold !important; color: #000 !important; }

    /* 確保導航欄文字放大 */
    .nav-bar { font-size: 16px !important; color: #AAA; margin-bottom: 10px; width: 100%; text-align: center; }
    .nav-active { color: #000000; font-weight: 400; }
    .breadcrumb { 
        background-color: #F8F9FA; 
        padding: 15px 15px !important; 
        border-radius: 15px; 
        font-size: 20px !important; /* 從 14px 放大至 20px */
        color: #333; 
        margin-bottom: 25px; 
        width: 100%; 
        text-align: center; 
        border: 1px solid #EAEAEA; 
    }
    hr { display: block !important; height: 1px !important; border: 0 !important; border-top: 1px solid #E0E0E0 !important; margin: 20px 0 !important; width: 100% !important; }

    /* *** 關鍵修改：強制放大 st.markdown 或 st.write 產生的所有普通內容文字 *** */
    [data-testid="stMarkdownContainer"] p {
        font-size: 24px !important; /* 確保所有主要的考核說明文字放大 */
        line-height: 1.6 !important; 
    }

    /* 確保按鈕文字也是平板友善的大小 */
    div.stButton > button p {
        font-size: 26px !important; 
        font-weight: 600 !important; 
    }
</style>
    """, unsafe_allow_html=True)

# --- 5. 輔助功能：帶顏色的明細表格 ---
def display_styled_df(df):
    """將狀況為否的文字設為紅色"""
    styled_df = df.style.apply(lambda x: ['color: red' if x['狀況'] == '否' else 'color: black' for _ in x], axis=1)
    st.table(styled_df)

# --- 6. 導覽列與初始化 ---
def render_nav(current_step):
    steps = {'select_trainer':"🎓訓練員",'select_type':"🍬職位",'select_name':"👤姓名",'select_main_pos':"🕒時段",'select_sub_pos':"📍區域",'assessment':"📝考核"}
    nav_html = " <span style='color:#DDD;'>/</span> ".join([f"<span class='{'nav-active' if k == current_step else ''}'>{v}</span>" for k, v in steps.items()])
    st.markdown(f"<div class='nav-bar'>{nav_html}</div>", unsafe_allow_html=True)

if 'step' not in st.session_state: st.session_state.step = 'select_trainer'
if 'complete' not in st.session_state: st.session_state.complete = False

# --- 7. 步驟流程渲染 ---
if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "rb") as f:
        st.download_button(
            label="下載歷史紀錄 (CSV)",
            data=f,
            file_name="history_log.csv",
            mime="text/csv"
        )
if st.session_state.step == 'view_history':
    st.markdown("## 📜 歷史考核摘要")
    
    if os.path.exists(HISTORY_FILE):
        h_df = pd.read_csv(HISTORY_FILE, encoding='utf-8-sig')
        st.table(h_df.tail(15).iloc[::-1])
    else: st.info("目前尚無紀錄。")
    if st.button("⬅️ 返回主選單"): st.session_state.step = 'select_trainer'; st.rerun()

elif st.session_state.step == 'view_staff_type':
    st.markdown("## 👥 選擇查看職位")
    if st.button("👤 正職人員"): 
        st.session_state.view_staff_type = "正職人員"
        st.session_state.step = 'view_staff_list'; st.rerun()
    if st.button("👫🏻 兼職人員"): 
        st.session_state.view_staff_type = "兼職人員"
        st.session_state.step = 'view_staff_list'; st.rerun()
    if st.button("⬅️ 返回主選單"): st.session_state.step = 'select_trainer'; st.rerun()

elif st.session_state.step == 'view_staff_list':
    st.markdown(f"## 👥 {st.session_state.view_staff_type} 紀錄")
    if os.path.exists(HISTORY_FILE):
        h_df = pd.read_csv(HISTORY_FILE, encoding='utf-8-sig')
        target_type = st.session_state.view_staff_type
        filtered_staff = h_df[h_df['職位'] == target_type]['受測人'].unique()
        unique_staff = sorted(filtered_staff)
        if len(unique_staff) > 0:
            for s_name in unique_staff:
                if st.button(s_name): 
                    st.session_state.view_target_staff = s_name
                    st.session_state.step = 'view_staff_detail'; st.rerun()
        else: st.info(f"目前尚無{target_type}的紀錄。")
    else: st.info("目前尚無紀錄。")
    if st.button("⬅️ 返回職位選擇"): st.session_state.step = 'view_staff_type'; st.rerun()

elif st.session_state.step == 'view_staff_detail':
    target = st.session_state.view_target_staff
    st.markdown(f"## 👤 {target} 的考核紀錄")
    pos_status = {}
    rec_file = os.path.join("records", f"{target}_考核表.xlsx")
    if os.path.exists(rec_file):
        try:
            xl = pd.ExcelFile(rec_file)
            if "訓練員名單" in xl.sheet_names:
                meta = xl.parse("訓練員名單")
                if "崗位" in meta.columns and "獨立操作" in meta.columns:
                    for _, row in meta.iterrows():
                        pos_status[str(row["崗位"])] = str(row["獨立操作"])
        except: pass
    st.markdown("##### 崗位考核狀態 (綠框:可獨立, 紅框:未獨立, 灰框:未考核)")
    raw_pos_list = (standards_df['崗位時段'].astype(str) + "-" + standards_df['崗位區域'].astype(str)).tolist()
    ordered_pos = []
    for item in raw_pos_list:
        if item not in ordered_pos: ordered_pos.append(item)
    pos_html = f"<div class='pos-container'>"
    for p in ordered_pos:
        status = pos_status.get(p, "無")
        css = "pos-tag"
        if status == "是": css += " pos-tag-yes"
        elif status == "否": css += " pos-tag-no"
        pos_html += f"<div class='{css}'>{p}</div>"
    pos_html += "</div>"
    st.markdown(pos_html, unsafe_allow_html=True)
    st.markdown("---")
    if os.path.exists(HISTORY_FILE):
        h_df = pd.read_csv(HISTORY_FILE, encoding='utf-8-sig')
        p_history = h_df[h_df['受測人'] == target].iloc[::-1]
        for idx, row in p_history.iterrows():
            with st.expander(f"📅 {row['時間']} | 🎓 {row['訓練員']} | 📍 {row['崗位']}"):
                sheet_name = row['崗位'][:31]
                try:
                    detail_df = pd.read_excel(rec_file, sheet_name=sheet_name)
                    display_styled_df(detail_df)
                except: st.warning("找不到詳細內容")
    if st.button("⬅️ 返回人員清單"): st.session_state.step = 'view_staff_list'; st.rerun()

elif st.session_state.step == 'select_trainer':
    render_nav('select_trainer')
    st.markdown("## 👑 選擇訓練員")
    for t in ["Joy", "吳致霖", "楊侑勳", "王煥睿"]:
        if st.button(t): st.session_state.trainer = t; st.session_state.step = 'select_type'; st.rerun()
    st.markdown("---")
    if st.button("👥 人員考核紀錄"): st.session_state.step = 'view_staff_type'; st.rerun()
    if st.button("📜 檢視歷史紀錄"): st.session_state.step = 'view_history'; st.rerun()

elif st.session_state.step == 'select_type':
    render_nav('select_type')
    st.markdown("## 🎓 受測人職位")
    if st.button("👤 正職人員"): st.session_state.staff_type = "正職人員"; st.session_state.step = 'select_name'; st.rerun()
    if st.button("👫🏻 兼職人員"): st.session_state.staff_type = "兼職人員"; st.session_state.step = 'select_name'; st.rerun()
    if st.button("⬅️ 返回"): st.session_state.step = 'select_trainer'; st.rerun()

elif st.session_state.step == 'select_name':
    render_nav('select_name')
    names = staff_df[staff_df['Type'] == st.session_state.staff_type]['Name'].tolist()
    for name in sorted(names):
        if st.button(name): st.session_state.selected_staff = name; st.session_state.step = 'select_main_pos'; st.rerun()
    if st.button("⬅️ 返回"): st.session_state.step = 'select_type'; st.rerun()

elif st.session_state.step == 'select_main_pos':
    render_nav('select_main_pos')
    time_slots = struct_df['時段'].unique().tolist()
    for slot in time_slots:
        if st.button(slot): st.session_state.main_pos = slot; st.session_state.step = 'select_sub_pos'; st.rerun()
    if st.button("⬅️ 返回"): st.session_state.step = 'select_name'; st.rerun()

elif st.session_state.step == 'select_sub_pos':
    render_nav('select_sub_pos')
    sub_positions = struct_df[struct_df['時段'] == st.session_state.main_pos]['區域'].unique()
    for sub in sub_positions:
        if st.button(sub): st.session_state.sub_pos = sub; st.session_state.step = 'assessment'; st.rerun()
    if st.button("⬅️ 返回"): st.session_state.step = 'select_main_pos'; st.rerun()

elif st.session_state.step == 'assessment':
    if st.session_state.complete:
        st.success(f"🎉 提交成功！")
        st.info(f"**摘要：** 🎓 訓練：{st.session_state.trainer} | 👤 受測：{st.session_state.selected_staff}\n📍 崗位：{st.session_state.main_pos}-{st.session_state.sub_pos} | 🛠️ 獨立：{st.session_state.last_indep}")
        if 'last_results_df' in st.session_state:
            with st.expander("查看本次評分明細"):
                display_styled_df(st.session_state.last_results_df)
        if st.button("🏠 返回首頁"):
            for k in ['trainer', 'staff_type', 'selected_staff', 'main_pos', 'sub_pos', 'complete', 'last_results_df', 'last_indep']: st.session_state.pop(k, None)
            st.session_state.step = 'select_trainer'; st.rerun()
    else:
        render_nav('assessment')
        st.markdown(f"<div class='breadcrumb'>👤 受測：{st.session_state.selected_staff} | 📍 崗位：{st.session_state.main_pos}-{st.session_state.sub_pos}</div>", unsafe_allow_html=True)
        target_file = os.path.join("Assessment", f"{st.session_state.main_pos}_{st.session_state.sub_pos}_考核內容.csv")
        try:
            content_df = pd.read_csv(target_file, encoding='utf-8-sig')
            items = content_df.iloc[:, 0].dropna().astype(str).tolist()
            results = {}
            for i, item in enumerate(items):
                st.markdown(f"**{i+1}. {item}**")
                results[item] = st.radio(f"r_{i}", ["是", "否"], index=None, horizontal=True, label_visibility="collapsed", key=f"eval_{i}")
                st.markdown("---")
            st.markdown("### 🛠️ 此崗位是否可獨立操作？")
            indep_op = st.radio("independent_op", ["是", "否"], index=None, horizontal=True, label_visibility="collapsed")
            
            # --- 核心修正：將所有邏輯封裝在按鈕觸發內 ---
            if st.button("✅ 提交考核表", key="submit_btn"):
                if None in results.values() or indep_op is None:
                    st.error("⚠️ 未完成評分及獨立操作選項。")
                else:
                    # --- 修正時區開始 ---
                    tw_tz = pytz.timezone('Asia/Taipei') 
                    now = datetime.now(tw_tz) 
                    # --- 修正時區結束 ---

                    staff_name = st.session_state.selected_staff
                    pos_name = f"{st.session_state.main_pos}-{st.session_state.sub_pos}"
                    file_path = os.path.join("records", f"{staff_name}_考核表.xlsx")
                    if not os.path.exists("records"): os.makedirs("records")
                    
                    # 建立本次考核的兩組資料
                    df_trainer_new = pd.DataFrame({
                        # 這裡的 now 已經帶有台灣時區
                        "考核日期": [now.strftime("%Y-%m-%d %H:%M")], 
                        "訓練員": [st.session_state.trainer], 
                        "崗位": [pos_name], 
                        "獨立操作": [indep_op]
                    })
                    df_results_new = pd.DataFrame(list(results.items()), columns=['考核內容', '狀況'])
                    
                    # --- 修正存檔邏輯：確保工作表結構正確 ---
                    if os.path.exists(file_path):
                        # 讀取現有的訓練員清單
                        try:
                            old_trainer_df = pd.read_excel(file_path, sheet_name="訓練員名單")
                            updated_trainer_df = pd.concat([old_trainer_df, df_trainer_new], ignore_index=True)
                        except:
                            updated_trainer_df = df_trainer_new

                        # 讀取所有現有的工作表，避免寫入時丟失其他崗位資料
                        all_sheets = {}
                        with pd.ExcelFile(file_path) as xls:
                            for sheet in xls.sheet_names:
                                if sheet != "訓練員名單": # 排除舊的總表，後面用更新後的取代
                                    all_sheets[sheet] = pd.read_excel(xls, sheet_name=sheet)

                        # 開始寫入
                        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                            updated_trainer_df.to_excel(writer, sheet_name="訓練員名單", index=False)
                            # 寫回原有的其他崗位資料
                            for s_name, s_df in all_sheets.items():
                                if s_name != pos_name[:31]: # 如果不是本次考核的崗位，就寫回
                                    s_df.to_excel(writer, sheet_name=s_name, index=False)
                            # 寫入本次考核的崗位細節
                            df_results_new.to_excel(writer, sheet_name=pos_name[:31], index=False)
                    else:
                        # 第一次建立檔案
                        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                            df_trainer_new.to_excel(writer, sheet_name="訓練員名單", index=False)
                            df_results_new.to_excel(writer, sheet_name=pos_name[:31], index=False)
                    
                    # 3. 儲存至歷史總表 (history_log.csv)
                    save_summary_to_history(st.session_state.trainer, staff_name, st.session_state.staff_type, pos_name)
                    
                    # 4. 同步雲端
                    with st.spinner("正在同步雲端備份..."):
                        sync_res = sync_to_cloud(file_path, f"{staff_name}_考核表.xlsx")
                        if "Success" in sync_res:
                            st.toast("☁️ 雲端備份成功！", icon="✅")
                        else:
                            st.toast("⚠️ 雲端同步失敗，檔案僅存於本地。", icon="❌")

                    # 更新狀態並跳轉
                    st.session_state.last_results_df = df_results_new
                    st.session_state.last_indep = indep_op
                    st.session_state.complete = True
                    st.rerun()

            # 🔹 新增返回首頁按鈕（在提交按鈕下方）
            if st.button("🏠 返回首頁", key="back_home_btn"):
                for k in ['trainer', 'staff_type', 'selected_staff', 'main_pos', 'sub_pos', 'complete', 'last_results_df', 'last_indep']: st.session_state.pop(k, None)
                st.session_state.step = 'select_trainer'; st.rerun()

        except Exception as e:
            st.warning(f"⚠️ 發生錯誤: {e}")
            if st.button("⬅️ 返回"): st.session_state.step = 'select_sub_pos'; st.rerun()














