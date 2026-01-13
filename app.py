import streamlit as st
import pandas as pd
from datetime import datetime
import os

# 1. 基本設定與 CSS 優化（適合手機觸控）
st.set_page_config(page_title="餐廳報廢系統", layout="centered")

# 使用 CSS 讓按鈕高度增加，方便手機點選
st.markdown("""
    <style>
    div.stButton > button {
        height: 3em;
        font-size: 1.1rem !important;
        margin-bottom: 10px;
    }
    .stNumberInput input {
        font-size: 1.5rem !important;
        height: 3em !important;
    }
    </style>
    """, unsafe_allow_html=True)

DATA_FILE = 'waste_records.csv'
DATA_MAP = {
    "大成食品": ["雞胸肉", "雞腿排", "雞翅"],
    "農夫市集": ["高麗菜", "牛番茄", "洋蔥", "青花菜"],
    "海鮮大王": ["草蝦", "鮭魚切片", "蛤蜊"],
    "調味專家": ["橄欖油", "黑胡椒", "玫瑰鹽"]
}

# 初始化 Session State
if 'selected_vendor' not in st.session_state: st.session_state.selected_vendor = None
if 'selected_item' not in st.session_state: st.session_state.selected_item = None
if 'show_reasons' not in st.session_state: st.session_state.show_reasons = False
if 'temp_record' not in st.session_state: st.session_state.temp_record = {}

# 確保 CSV 存在
if not os.path.exists(DATA_FILE):
    df_init = pd.DataFrame(columns=["輸入時間", "廠商", "品項", "重量(g)", "報廢原因"])
    df_init.to_csv(DATA_FILE, index=False, encoding='utf-8-sig')

# --- 2. 頁面分頁設計 (適合平板切換) ---
tab1, tab2 = st.tabs(["📝 報廢登記", "📊 歷史紀錄"])

with tab1:
    st.header("餐廳報廢登記")

    # 步驟 1: 選擇廠商 (按鈕改為 2 列排版適合手機)
    st.subheader("1. 選擇廠商")
    vendors = list(DATA_MAP.keys())
    v_cols = st.columns(2) 
    for i, v_name in enumerate(vendors):
        with v_cols[i % 2]:
            if st.button(v_name, use_container_width=True):
                st.session_state.selected_vendor = v_name
                st.session_state.selected_item = None
                st.session_state.show_reasons = False

    # 步驟 2: 選擇品項
    if st.session_state.selected_vendor:
        st.divider()
        st.subheader(f"2. 選擇品項 ({st.session_state.selected_vendor})")
        items = DATA_MAP[st.session_state.selected_vendor]
        i_cols = st.columns(2)
        for i, item_name in enumerate(items):
            with i_cols[i % 2]:
                if st.button(item_name, use_container_width=True):
                    st.session_state.selected_item = item_name
                    st.session_state.show_reasons = False

    # 步驟 3: 輸入重量
    if st.session_state.selected_item:
        st.divider()
        st.info(f"📍 已選：{st.session_state.selected_vendor} / {st.session_state.selected_item}")
        weight = st.number_input("3. 輸入重量 (克)", min_value=1, step=50, key="weight_input")
        
        if st.button("確認重量並選擇原因 ➔", type="primary", use_container_width=True):
            st.session_state.temp_record = {
                "輸入時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "廠商": st.session_state.selected_vendor,
                "品項": st.session_state.selected_item,
                "重量(g)": weight
            }
            st.session_state.show_reasons = True

    # 步驟 4: 報廢原因 (全螢幕大按鈕)
    if st.session_state.get("show_reasons"):
        st.markdown("---")
        st.warning("最後一步：請點選報廢原因")
        reasons = ["基本損耗", "客人退貨", "品質不佳", "掉落地面"]
        
        # 原因按鈕採用單欄大按鈕，方便大拇指點選
        for reason in reasons:
            if st.button(reason, use_container_width=True, key=f"reason_{reason}"):
                final_data = st.session_state.temp_record
                final_data["報廢原因"] = reason
                
                df = pd.read_csv(DATA_FILE)
                df = pd.concat([df, pd.DataFrame([final_data])], ignore_index=True)
                df.to_csv(DATA_FILE, index=False, encoding='utf-8-sig')
                
                st.success("✅ 登記成功！資料已儲存。")
                st.session_state.selected_vendor = None
                st.session_state.selected_item = None
                st.session_state.show_reasons = False
                st.rerun()

with tab2:
    st.header("最近登記紀錄")
    if os.path.exists(DATA_FILE):
        history_df = pd.read_csv(DATA_FILE)
        if not history_df.empty:
            # 只顯示最近三筆，並優化表格顯示
            st.write("顯示最近 3 筆資料：")
            st.dataframe(history_df.tail(3).iloc[::-1], use_container_width=True)
            
            # 提供完整下載
            with open(DATA_FILE, "rb") as f:
                st.download_button(
                    label="📥 下載完整 CSV 報表",
                    data=f,
                    file_name=f"報廢紀錄_{datetime.now().strftime('%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.info("目前尚無登記資料")
