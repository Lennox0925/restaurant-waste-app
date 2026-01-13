import streamlit as st
import pandas as pd
from datetime import datetime, timedelta  # 引入 timedelta 處理時區
import os

# 設定檔案路徑
DATA_FILE = 'waste_records.csv'
MENU_FILE = 'menu.csv'

# --- 獲取台灣時間函數 ---
def get_taiwan_time():
    # Streamlit Cloud 預設是 UTC，手動加 8 小時轉為台灣時間
    return datetime.utcnow() + timedelta(hours=8)

# --- 設定頁面與樣式 ---
st.set_page_config(page_title="餐廳報廢系統", layout="centered")
st.markdown("""
    <style>
    div.stButton > button { height: 3.5em; font-size: 1.1rem !important; margin-bottom: 10px; }
    .stNumberInput input { font-size: 1.5rem !important; height: 3em !important; }
    .stAlert { font-size: 1.2rem !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 讀取外部選單資料 ---
@st.cache_data
def load_menu():
    if os.path.exists(MENU_FILE):
        try:
            df_menu = pd.read_csv(MENU_FILE)
            return df_menu
        except:
            st.error("menu.csv 讀取失敗，請檢查編碼或欄位")
            return pd.DataFrame(columns=["類別", "廠商", "品項"])
    return pd.DataFrame(columns=["類別", "廠商", "品項"])

df_menu_raw = load_menu()

# --- 初始化 Session State ---
if 'page' not in st.session_state: st.session_state.page = "登記"
if 'step' not in st.session_state: st.session_state.step = 1
if 'selected_cat' not in st.session_state: st.session_state.selected_cat = None
if 'selected_vendor' not in st.session_state: st.session_state.selected_vendor = None
if 'selected_item' not in st.session_state: st.session_state.selected_item = None

# 確保紀錄檔存在且欄位正確
COLUMNS = ["輸入時間", "類別", "廠商", "品項", "重量(g)", "報廢原因"]
if not os.path.exists(DATA_FILE):
    pd.DataFrame(columns=COLUMNS).to_csv(DATA_FILE, index=False, encoding='utf-8-sig')

# --- 頁面邏輯切換 ---
col_nav1, col_nav2 = st.columns(2)
if col_nav1.button("📝 進入登記"): 
    st.session_state.page = "登記"
    st.rerun()
if col_nav2.button("📊 查看紀錄"): 
    st.session_state.page = "紀錄"
    st.rerun()

st.divider()

# --- A. 登記頁面 ---
if st.session_state.page == "登記":
    st.header("🍎 報廢登記")
    
    if st.session_state.step == 1:
        st.info("💡 提示：當月 1 號輸入前請先前往紀錄頁清除資料")
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
        st.info(f"📍 已選：{st.session_state.selected_cat} > {st.session_state.selected_item}")
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
                # --- 修改點：使用 get_taiwan_time() 獲取修正後的時間 ---
                now_tw = get_taiwan_time()
                new_data = {
                    "輸入時間": now_tw.strftime("%Y-%m-%d %H:%M"),
                    "類別": st.session_state.selected_cat,
                    "廠商": st.session_state.selected_vendor,
                    "品項": st.session_state.selected_item,
                    "重量(g)": st.session_state.temp_weight,
                    "報廢原因": reason
                }
                df = pd.read_csv(DATA_FILE)
                df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                df.to_csv(DATA_FILE, index=False, encoding='utf-8-sig')
                
                st.session_state.page = "紀錄" 
                st.session_state.step = 1
                st.rerun()

# --- B. 紀錄頁面 ---
elif st.session_state.page == "紀錄":
    st.header("📊 最近登記紀錄")
    if os.path.exists(DATA_FILE):
        history_df = pd.read_csv(DATA_FILE)
        if not history_df.empty:
            st.table(history_df[COLUMNS].tail(3).iloc[::-1])
            st.divider()
            
            if st.button("➕ 繼續登記下一筆", type="primary", use_container_width=True):
                st.session_state.page = "登記"
                st.session_state.step = 1
                st.rerun()
                
            csv_data = history_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            # 檔名也使用台灣時間
            file_date = get_taiwan_time().strftime('%Y%m%d')
            st.download_button(
                label="📥 下載完整 CSV 報表",
                data=csv_data,
                file_name=f"waste_report_{file_date}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            st.write("---")
            with st.expander("🛠️ 管理員功能 (清除資料)"):
                pwd = st.text_input("請輸入管理密碼", type="password")
                if st.button("確認永久刪除所有紀錄", type="secondary", use_container_width=True):
                    if pwd == "85129111":
                        pd.DataFrame(columns=COLUMNS).to_csv(DATA_FILE, index=False, encoding='utf-8-sig')
                        st.success("檔案內容已清空！")
                        st.rerun()
                    else:
                        st.error("密碼錯誤，無法刪除。")
        else:
            st.info("目前尚無資料")
            if st.button("返回登記"):
                st.session_state.page = "登記"
                st.rerun()
