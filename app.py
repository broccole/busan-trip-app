import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# ==========================================
# 設定與連線
# ==========================================
st.set_page_config(page_title="釜山五日遊 (雲端版)", page_icon="☁️", layout="wide")
st.markdown("""
<style>
    /* 1. 調整分頁標籤字體 (這是原本的) */
    .stTabs [data-baseweb="tab"] {
        font-size: 20px;
        font-weight: bold;
    }

    /* 2. 這裡新增：調整標題 (st.title) 的字體大小 */
    h1 {
        font-size: 32px !important;  /* 數字越小字越小，預設大約是 44px */
    }
</style>
""", unsafe_allow_html=True)

# Google Sheets 檔案名稱 (必須跟你建立的一模一樣)
SHEET_NAME = "Busan_Trip_DB"

def get_google_sheet_client():
    """連線到 Google Sheets"""
    # 從 secrets.toml 讀取金鑰資訊
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = st.secrets["gcp_service_account"]
    
    # 建立憑證
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# 快取連線物件，避免每次動作都重新連線
@st.cache_resource
def get_worksheet(worksheet_name):
    client = get_google_sheet_client()
    sheet = client.open(SHEET_NAME)
    return sheet.worksheet(worksheet_name)

# ==========================================
# 資料讀取/寫入函數 (雲端版)
# ==========================================

def load_expenses():
    """從 Google Sheet 讀取記帳"""
    try:
        ws = get_worksheet("Expenses")
        data = ws.get_all_records() # 讀取所有資料
        df = pd.DataFrame(data)
        # 確保欄位存在，避免空表報錯
        if df.empty:
            return pd.DataFrame(columns=['日期', '項目', '類別', '金額'])
        return df
    except Exception as e:
        st.error(f"讀取記帳失敗: {e}")
        return pd.DataFrame(columns=['日期', '項目', '類別', '金額'])

def save_expense(date, item, category, amount):
    """寫入一筆記帳到 Google Sheet"""
    ws = get_worksheet("Expenses")
    # append_row 會直接加在最後一行
    # date 若是 datetime 物件，轉成字串
    ws.append_row([str(date), item, category, amount])

def load_itinerary():
    """從 Google Sheet 讀取行程，並轉換成我們先前的 JSON 格式結構"""
    try:
        ws = get_worksheet("Itinerary")
        data = ws.get_all_records()
        
        # 如果是空的，回傳預設結構
        if not data:
            return {"Day 1": [], "Day 2": [], "Day 3": [], "Day 4": [], "Day 5": []}

        # 將平面表格資料轉換回 Dictionary 結構: {"Day 1": [...], "Day 2": [...]}
        itinerary_dict = {"Day 1": [], "Day 2": [], "Day 3": [], "Day 4": [], "Day 5": []}
        
        for row in data:
            day = row.get('Day', 'Day 1')
            if day not in itinerary_dict:
                itinerary_dict[day] = []
            
            itinerary_dict[day].append({
                "time": row.get('Time', ''),
                "title": row.get('Title', ''),
                "desc": row.get('Desc', ''),
                "link": row.get('Link', '')
            })
            
        return itinerary_dict
    except Exception as e:
        st.error(f"讀取行程失敗: {e}")
        return {"Day 1": [], "Day 2": [], "Day 3": [], "Day 4": [], "Day 5": []}

def save_itinerary_full(data_dict):
    """
    將完整的行程 Dictionary 寫回 Google Sheet (全量更新)
    注意：這會清空原本的表，重新寫入，這在資料量不大時是最簡單的做法。
    """
    ws = get_worksheet("Itinerary")
    ws.clear() # 清空舊資料
    
    # 寫入標題
    ws.append_row(["Day", "Time", "Title", "Desc", "Link"])
    
    # 準備要寫入的資料列
    rows_to_write = []
    for day, activities in data_dict.items():
        for act in activities:
            rows_to_write.append([
                day,
                act.get('time', ''),
                act.get('title', ''),
                act.get('desc', ''),
                act.get('link', '')
            ])
    
    if rows_to_write:
        ws.append_rows(rows_to_write)

# ==========================================
# 頁面 UI (與之前幾乎相同，只改了資料呼叫)
# ==========================================

def page_overview():
    st.title("🇰🇷 釜山五天")
    # 請換回你自己的圖片檔名
    st.image("釜山纜車松島.webp", caption="Busan, Cloud Edition", use_container_width=True)
    st.success("☁️記得下載NAVER MAP! (google maps 在韓國會失靈)")

def page_itinerary():
    st.title("📅 每日行程概覽")
    
    # 讀取
    itinerary_data = load_itinerary()
    
    col_ctrl1, col_ctrl2 = st.columns([3, 1])
    with col_ctrl1:
        st.caption("所有變更都會同步到 Google Drive。")
    with col_ctrl2:
        is_edit_mode = st.toggle("✏️ 編輯模式", value=False)
    
    # 確保所有天數都有 key
    all_days = ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5"]
    for d in all_days:
        if d not in itinerary_data:
            itinerary_data[d] = []
            
    tabs = st.tabs(all_days)
    
    for i, day in enumerate(all_days):
        with tabs[i]:
            activities = itinerary_data[day]
            # 排序
            activities.sort(key=lambda x: x.get('time', '00:00'))
            
            indices_to_delete = []

            for idx, activity in enumerate(activities):
                time_val = activity.get('time', '')
                title_val = activity.get('title', '')
                desc_val = activity.get('desc', '')
                link_val = activity.get('link', '')

                with st.expander(f"🕒 {time_val} - {title_val}", expanded=True):
                    if is_edit_mode:
                        c1, c2 = st.columns([1, 2])
                        new_time = c1.text_input("時間", time_val, key=f"t_{day}_{idx}")
                        new_title = c2.text_input("標題", title_val, key=f"ti_{day}_{idx}")
                        new_desc = st.text_area("說明", desc_val, key=f"d_{day}_{idx}")
                        c3, c4 = st.columns([4, 1])
                        new_link = c3.text_input("Map 連結", link_val, key=f"lnk_{day}_{idx}")
                        
                        if c4.button("🗑️ 刪除", key=f"del_{day}_{idx}", type="primary"):
                            indices_to_delete.append(idx)
                        
                        # 更新暫存
                        activity['time'] = new_time
                        activity['title'] = new_title
                        activity['desc'] = new_desc
                        activity['link'] = new_link
                    else:
                        st.write(desc_val)
                        if link_val:
                            st.markdown(f"📍 [開啟地圖]({link_val})")
            
            if is_edit_mode:
                st.markdown("---")
                c_add, c_save = st.columns([1, 4])
                
                if c_add.button("➕ 新增", key=f"add_{day}"):
                    activities.append({"time": "09:00", "title": "新行程", "desc": "", "link": ""})
                    # 這裡先不存雲端，等使用者按儲存或切換時存，但為了體驗好，我們直接全量存一次
                    itinerary_data[day] = activities
                    save_itinerary_full(itinerary_data)
                    st.rerun()

                if indices_to_delete:
                    # 刪除邏輯
                    target_idx = indices_to_delete[0]
                    del activities[target_idx]
                    itinerary_data[day] = activities
                    save_itinerary_full(itinerary_data)
                    st.success("已刪除並同步雲端！")
                    st.rerun()
                
                if c_save.button("💾 儲存變更", key=f"save_{day}"):
                    itinerary_data[day] = activities
                    save_itinerary_full(itinerary_data)
                    st.success("已儲存至 Google Sheets！")

def page_expenses():
    st.title("💰 旅費記帳 (雲端)")
    
    with st.container():
        st.subheader("➕ 新增消費")
        with st.form("expense_form", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
            date_inp = c1.date_input("日期")
            item_inp = c2.text_input("項目")
            cat_inp = c3.selectbox("類別", ["飲食", "交通", "住宿", "購物", "娛樂", "其他"])
            amt_inp = c4.number_input("金額", min_value=0, step=100)
            
            if st.form_submit_button("新增"):
                if item_inp and amt_inp > 0:
                    save_expense(date_inp, item_inp, cat_inp, amt_inp)
                    st.success(f"已上傳雲端：{item_inp} ${amt_inp}")
                    # 清除快取，讓下方的表格重新讀取最新資料
                    st.cache_data.clear()
                    st.rerun()

    st.markdown("---")
    # 這裡我們不 cache load_expenses，因為想要即時看到新增的資料
    # 但為了效能，通常可以加一點 cache，這裡為了簡單直接讀
    df = load_expenses()
    
    if not df.empty:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("📋 明細")
            # 轉換金額為數字確保圖表正常 (防呆)
            df['金額'] = pd.to_numeric(df['金額'], errors='coerce').fillna(0)
            st.dataframe(df, use_container_width=True)
        with c2:
            st.subheader("📊 統計")
            total = df['金額'].sum()
            st.metric("總花費", f"${total:,.0f}")
            chart_data = df.groupby('類別')['金額'].sum()
            st.bar_chart(chart_data)
    else:
        st.info("雲端表格是空的，快去記一筆吧！")

def main():
    st.sidebar.title("☁️ 釜山旅遊")
    menu = st.sidebar.radio("導航", ["行程總覽", "每日行程", "旅費記帳"])
    
    if menu == "行程總覽":
        page_overview()
    elif menu == "每日行程":
        page_itinerary()
    elif menu == "旅費記帳":
        page_expenses()

if __name__ == "__main__":

    main()


