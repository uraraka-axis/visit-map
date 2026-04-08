"""
営業訪問先マップ - メインページ
Streamlit + Supabase + Leaflet(folium)
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
from supabase import create_client
import pandas as pd
from datetime import date
import io
import re

st.set_page_config(page_title="営業訪問先マップ", layout="wide")

# ステータス定義（マーカー色・CSS色）
STATUS_CONFIG = {
    "未訪問": {"color": "#e74c3c"},
    "アポ済": {"color": "#f39c12"},
    "訪問済": {"color": "#27ae60"},
    "対象外": {"color": "#95a5a6"},
}


# =======================================================
# Supabase接続
# =======================================================
@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def load_hotels(area=None):
    query = get_db().table("hotels").select("*").order("id")
    if area:
        query = query.eq("area", area)
    res = query.execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()


def load_areas():
    res = get_db().table("hotels").select("area").execute()
    if res.data:
        return sorted(set(r["area"] for r in res.data))
    return []


def save_hotel(hotel_id, data):
    get_db().table("hotels").update(data).eq("id", hotel_id).execute()


def parse_rooms(val):
    if pd.isna(val) or not str(val).strip():
        return None
    nums = re.findall(r"\d+", str(val))
    return int(nums[0]) if nums else None


# =======================================================
# CSS
# =======================================================
st.markdown("""
<style>
[data-testid="stSidebarNav"] { display: none !important; }
[data-testid="stSidebar"] h1 {
    font-size: 1.3rem;
    font-weight: 600;
    letter-spacing: 0.02em;
}
.stat-row {
    display: flex;
    align-items: center;
    padding: 3px 0;
    font-size: 0.9rem;
}
.stat-row .dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    margin-right: 8px;
    flex-shrink: 0;
}
.stat-row .label { color: #555; }
.stat-row .count { margin-left: auto; font-weight: 600; }
.stat-total {
    border-top: 1px solid #ddd;
    margin-top: 6px;
    padding-top: 6px;
    font-size: 0.9rem;
    font-weight: 600;
}
.mobile-title {
    display: none;
    font-size: 1.2rem;
    font-weight: 600;
    margin: 0 0 8px 0;
    padding: 0;
}
@media (max-width: 768px) {
    [data-testid="stSidebar"] { min-width: 260px !important; max-width: 260px !important; }
    [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        width: 100% !important; flex: 0 0 100% !important; min-width: 100% !important;
    }
    .leaflet-popup-content { font-size: 14px !important; }
    .mobile-title { display: block; }
}
</style>
""", unsafe_allow_html=True)

# スマホ用タイトル（PCではサイドバーにあるため非表示）
st.markdown('<h2 class="mobile-title">営業訪問先マップ</h2>', unsafe_allow_html=True)

# =======================================================
# サイドバー
# =======================================================
st.sidebar.title("営業訪問先マップ")

areas = load_areas()
if not areas:
    st.warning("データがありません。\n左メニューの「データインポート」からExcelを取り込んでください。")
    st.stop()

selected_area = st.sidebar.selectbox("エリア", areas)

df_all = load_hotels(selected_area)
if df_all.empty:
    st.info(f"{selected_area} のデータはありません。")
    st.stop()

if "status" not in df_all.columns:
    df_all["status"] = "未訪問"
df_all["status"] = df_all["status"].fillna("未訪問")

# --- フィルタ ---
st.sidebar.markdown("---")
st.sidebar.markdown("**ステータス**")

show_statuses = []
for status, conf in STATUS_CONFIG.items():
    checked = status != "対象外"
    if st.sidebar.checkbox(status, value=checked, key=f"chk_{status}"):
        show_statuses.append(status)

# 客室数フィルタ
df_all["_rooms_num"] = df_all["rooms"].apply(parse_rooms)
rooms_valid = df_all["_rooms_num"].dropna()
if not rooms_valid.empty:
    r_min = int(rooms_valid.min())
    r_max = int(rooms_valid.max())
    if r_min < r_max:
        default_min = max(r_min, 50)
        room_range = st.sidebar.slider(
            "客室数", r_min, r_max, (default_min, r_max), key="room_filter"
        )
    else:
        room_range = None
else:
    room_range = None

# フィルタ適用
df = df_all[df_all["status"].isin(show_statuses)].copy()
if room_range:
    df = df[
        (df["_rooms_num"].isna()) |
        ((df["_rooms_num"] >= room_range[0]) & (df["_rooms_num"] <= room_range[1]))
    ]

# --- 統計（フィルタ後の件数、HTMLカラードット） ---
df_room_filtered = df_all.copy()
if room_range:
    df_room_filtered = df_room_filtered[
        (df_room_filtered["_rooms_num"].isna()) |
        ((df_room_filtered["_rooms_num"] >= room_range[0]) & (df_room_filtered["_rooms_num"] <= room_range[1]))
    ]

st.sidebar.markdown("---")
stat_html = ""
for status, conf in STATUS_CONFIG.items():
    cnt = len(df_room_filtered[df_room_filtered["status"] == status])
    stat_html += (
        f'<div class="stat-row">'
        f'<div class="dot" style="background:{conf["color"]};"></div>'
        f'<span class="label">{status}</span>'
        f'<span class="count">{cnt}</span>'
        f'</div>'
    )
stat_html += f'<div class="stat-total">合計　{len(df_room_filtered)} 件</div>'
st.sidebar.markdown(stat_html, unsafe_allow_html=True)

# --- ナビゲーション（サイドバー下部） ---
st.sidebar.markdown("---")
st.sidebar.page_link("streamlit_app.py", label="地図一覧")
st.sidebar.page_link("pages/01_データインポート.py", label="データインポート")


# =======================================================
# メインエリア（フラグメント化で部分再実行）
# =======================================================
if df.empty:
    st.info("表示対象がありません")
    st.stop()

names_list = df["name"].tolist()

# 初回は未選択状態（None）
if "selected_hotel" not in st.session_state:
    st.session_state.selected_hotel = None
if st.session_state.selected_hotel not in names_list:
    st.session_state.selected_hotel = None


@st.fragment
def main_content():
    col_map, col_edit = st.columns([3, 1])

    # --- マップ ---
    with col_map:
        geo_df = df.dropna(subset=["lat", "lng"])

        # 中心・ズームはエリア単位で初回のみ確定（選択で動かさない）
        view_key = f"map_view_{selected_area}"
        if view_key not in st.session_state:
            if not geo_df.empty:
                st.session_state[view_key] = {
                    "center": [geo_df["lat"].mean(), geo_df["lng"].mean()],
                    "zoom": 14,
                }
            else:
                st.session_state[view_key] = {"center": [35.1, 139.07], "zoom": 14}

        view = st.session_state[view_key]
        m = folium.Map(location=view["center"], zoom_start=view["zoom"], tiles="CartoDB Voyager")

        for _, row in geo_df.iterrows():
            conf = STATUS_CONFIG.get(row["status"], STATUS_CONFIG["未訪問"])
            gmap_url = f"https://www.google.com/maps?q={row['lat']},{row['lng']}"

            popup_lines = [f"<b>{row['name']}</b>"]
            if row.get("address"):
                popup_lines.append(row["address"])
            if row.get("phone"):
                popup_lines.append(f"TEL: {row['phone']}")
            if row.get("rooms"):
                popup_lines.append(f"客室数: {row['rooms']}")
            popup_lines.append(
                f'<a href="{gmap_url}" target="_blank" '
                f'style="color:#1a73e8;text-decoration:none;">'
                f'Googleマップで開く &rarr;</a>'
            )
            popup_html = "<br>".join(popup_lines)

            dot_html = (
                f'<div style="'
                f'width:14px;height:14px;'
                f'border-radius:50%;'
                f'background:{conf["color"]};'
                f'border:2px solid #fff;'
                f'box-shadow:0 1px 4px rgba(0,0,0,0.3);'
                f'"></div>'
            )
            icon = folium.DivIcon(
                html=dot_html,
                icon_size=(14, 14),
                icon_anchor=(7, 7),
            )
            folium.Marker(
                location=[row["lat"], row["lng"]],
                popup=folium.Popup(popup_html, max_width=280),
                tooltip=row["name"],
                icon=icon,
            ).add_to(m)

        map_result = st_folium(
            m, width=None, height=700,
            returned_objects=["last_object_clicked", "last_object_clicked_tooltip"],
            key=f"main_map_{selected_area}",
        )

        clicked_name = None
        if map_result:
            # tooltip（施設名）で直接特定
            tip = map_result.get("last_object_clicked_tooltip")
            if tip and tip in names_list:
                clicked_name = tip
            # fallback: 座標で特定
            elif map_result.get("last_object_clicked"):
                clicked = map_result["last_object_clicked"]
                for _, row in df.iterrows():
                    if (pd.notna(row.get("lat")) and pd.notna(row.get("lng"))
                            and abs(row["lat"] - clicked["lat"]) < 0.0001
                            and abs(row["lng"] - clicked["lng"]) < 0.0001):
                        clicked_name = row["name"]
                        break

        if clicked_name and clicked_name != st.session_state.selected_hotel:
            st.session_state.selected_hotel = clicked_name
            st.session_state.hotel_select = clicked_name
            # 手動 rerun は不要（st_folium の戻り値変化で fragment が自然に再実行される）

    # --- 施設選択・編集 ---
    with col_edit:
        st.markdown("### 施設情報")

        # 未選択時は先頭に「--」を表示
        select_names = ["--"] + names_list
        if st.session_state.selected_hotel and st.session_state.selected_hotel in names_list:
            current_idx = select_names.index(st.session_state.selected_hotel)
        else:
            current_idx = 0

        chosen_name = st.selectbox(
            "施設を選択", select_names, index=current_idx, key="hotel_select"
        )

        if chosen_name == "--":
            if st.session_state.selected_hotel is not None:
                st.session_state.selected_hotel = None
                st.rerun(scope="fragment")
            st.caption("ピンをクリックまたは施設を選択してください")
            return

        if chosen_name != st.session_state.selected_hotel:
            st.session_state.selected_hotel = chosen_name
            st.rerun(scope="fragment")

        hotel = df[df["name"] == chosen_name].iloc[0]

        st.caption(f"{hotel.get('address', '') or '---'}")
        st.caption(f"TEL: {hotel.get('phone', '') or '---'}")
        st.caption(f"客室数: {hotel.get('rooms', '') or '---'}")
        if hotel.get("website"):
            st.caption(f"[ウェブサイト]({hotel['website']})")
        if pd.notna(hotel.get("lat")) and pd.notna(hotel.get("lng")):
            gmap_url = f"https://www.google.com/maps?q={hotel['lat']},{hotel['lng']}"
            st.caption(f"[Googleマップで開く]({gmap_url})")

        st.markdown("---")
        st.markdown("### 営業実績")

        status_list = list(STATUS_CONFIG.keys())
        current_status_idx = status_list.index(hotel["status"]) if hotel["status"] in status_list else 0
        new_status = st.selectbox("ステータス", status_list, index=current_status_idx, key="edit_status")

        visit_val = None
        if pd.notna(hotel.get("visit_date")) and hotel["visit_date"]:
            try:
                visit_val = pd.to_datetime(hotel["visit_date"]).date()
            except Exception:
                pass
        new_date = st.date_input("訪問日", value=visit_val or date.today(), key="edit_date")

        new_memo = st.text_area("メモ", value=hotel.get("memo", "") or "", height=100, key="edit_memo")

        if st.button("保存", type="primary", use_container_width=True):
            save_hotel(hotel["id"], {
                "status": new_status,
                "visit_date": str(new_date),
                "memo": new_memo,
            })
            st.success("保存しました")
            st.rerun()


main_content()

# =======================================================
# 下部: 一覧テーブル + エクスポート
# =======================================================
st.markdown("---")

tab_list, tab_export = st.tabs(["施設一覧", "エクスポート"])

with tab_list:
    display_cols = {
        "name": "施設名",
        "status": "ステータス",
        "rooms": "客室数",
        "address": "住所",
        "phone": "電話番号",
        "visit_date": "訪問日",
        "memo": "メモ",
    }
    cols = [c for c in display_cols if c in df.columns]
    st.dataframe(
        df[cols].rename(columns=display_cols),
        use_container_width=True,
        height=350,
    )

with tab_export:
    st.markdown("現在のフィルタ条件でExcelファイルをダウンロードします。")
    buf = io.BytesIO()
    export_cols = [c for c in display_cols if c in df.columns]
    df_export = df[export_cols].rename(columns=display_cols)
    df_export.insert(0, "No.", range(1, len(df_export) + 1))
    df_export.to_excel(buf, index=False, sheet_name=selected_area)
    st.download_button(
        label="Excelダウンロード",
        data=buf.getvalue(),
        file_name=f"{selected_area}_営業実績.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
