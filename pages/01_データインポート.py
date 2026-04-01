"""
データインポート - スクレイピング結果のExcelをSupabaseに取り込む
"""

import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(page_title="データインポート", layout="wide")

# デフォルトナビゲーションを非表示
st.markdown('<style>[data-testid="stSidebarNav"] { display: none !important; }</style>', unsafe_allow_html=True)

st.title("データインポート")

# サイドバーにナビゲーション
st.sidebar.page_link("streamlit_app.py", label="地図一覧")
st.sidebar.page_link("pages/01_データインポート.py", label="データインポート")
st.sidebar.markdown("---")


@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


# 列マッピング
COL_MAP = {
    "宿泊施設名": "name",
    "客室数": "rooms",
    "住所": "address",
    "電話番号": "phone",
    "ウェブサイトURL": "website",
    "緯度": "lat",
    "経度": "lng",
}

tab_import, tab_delete = st.tabs(["インポート", "データ削除"])

# =======================================================
# インポートタブ
# =======================================================
with tab_import:
    st.caption("スクレイピングツールで出力したExcelファイルをアップロードして、Supabaseに取り込みます。")

    uploaded = st.file_uploader("Excelファイルを選択", type=["xlsx", "xls"])

    if not uploaded:
        st.info("スクレイピングツールで出力した `.xlsx` ファイルをドラッグ＆ドロップしてください。")
        st.markdown("""
        **対応フォーマット:**
        | 列 | 内容 |
        |---|---|
        | No. | 連番 |
        | 宿泊施設名 | 施設名（必須） |
        | 客室数 | 部屋数 |
        | 住所 | 住所 |
        | 電話番号 | TEL |
        | ウェブサイトURL | URL |
        | 緯度 | lat（あれば） |
        | 経度 | lng（あれば） |
        """)
    else:
        # Excelを読み込み
        df = pd.read_excel(uploaded, sheet_name=0)
        st.markdown(f"**読み込み: {len(df)} 件**")
        st.dataframe(df.head(10), use_container_width=True)

        # インポート設定
        st.markdown("---")
        st.markdown("### インポート設定")

        # エリア名（ファイル名から推定）
        fname = uploaded.name.replace(".xlsx", "").replace(".xls", "")
        area_guess = fname.split("_")[0] if "_" in fname else fname
        area_name = st.text_input("エリア名（識別用）", value=area_guess,
                                  help="同じエリア名で再インポートすると既存データを更新します")

        if not area_name.strip():
            st.warning("エリア名を入力してください")
            st.stop()

        # マッピング確認
        st.markdown("### 列マッピング確認")
        mapped = {}
        for jp_col, db_col in COL_MAP.items():
            if jp_col in df.columns:
                mapped[jp_col] = db_col
                st.success(f"✓ {jp_col} → {db_col}")
            else:
                st.warning(f"△ {jp_col} 列なし（スキップ）")

        name_col = "宿泊施設名"
        if name_col not in df.columns:
            st.error(f"「{name_col}」列が見つかりません。正しいExcelファイルか確認してください。")
            st.stop()

        # インポート実行
        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            mode = st.radio("インポートモード", ["新規追加＋既存更新（推奨）", "全置換（既存データ削除）"])
        with col2:
            st.markdown(f"""
            **インポート内容:**
            - エリア: **{area_name}**
            - 件数: **{len(df)}** 件
            - 位置情報: **{df['緯度'].notna().sum() if '緯度' in df.columns else 0}** 件
            """)

        if st.button("インポート実行", type="primary"):
            db = get_db()
            progress = st.progress(0)
            status_text = st.empty()

            # 全置換モード: 既存データ削除
            if "全置換" in mode:
                status_text.text(f"{area_name} の既存データを削除中...")
                db.table("hotels").delete().eq("area", area_name).execute()

            success_count = 0
            error_count = 0

            for i, row in df.iterrows():
                name = str(row.get(name_col, "")).strip()
                if not name:
                    continue

                record = {
                    "area": area_name,
                    "name": name,
                    "rooms": str(row.get("客室数", "")) if pd.notna(row.get("客室数")) else "",
                    "address": str(row.get("住所", "")) if pd.notna(row.get("住所")) else "",
                    "phone": str(row.get("電話番号", "")) if pd.notna(row.get("電話番号")) else "",
                    "website": str(row.get("ウェブサイトURL", "")) if pd.notna(row.get("ウェブサイトURL")) else "",
                }

                # 緯度経度
                if "緯度" in df.columns and pd.notna(row.get("緯度")):
                    try:
                        record["lat"] = float(row["緯度"])
                    except (ValueError, TypeError):
                        pass
                if "経度" in df.columns and pd.notna(row.get("経度")):
                    try:
                        record["lng"] = float(row["経度"])
                    except (ValueError, TypeError):
                        pass

                try:
                    db.table("hotels").upsert(
                        record,
                        on_conflict="area,name"
                    ).execute()
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    if error_count <= 3:
                        st.warning(f"エラー ({name}): {str(e)[:80]}")

                progress.progress((i + 1) / len(df))
                status_text.text(f"処理中... {i + 1}/{len(df)}")

            progress.progress(1.0)
            status_text.empty()

            if error_count == 0:
                st.success(f"インポート完了！ {success_count} 件を取り込みました。")
            else:
                st.warning(f"完了（成功: {success_count} / エラー: {error_count}）")

# =======================================================
# データ削除タブ
# =======================================================
with tab_delete:
    st.markdown("### エリアデータ削除")
    st.caption("指定したエリアのデータをすべて削除します。")

    db_del = get_db()
    res = db_del.table("hotels").select("area").execute()
    if res.data:
        area_list = sorted(set(r["area"] for r in res.data))
        area_counts = {}
        for r in res.data:
            area_counts[r["area"]] = area_counts.get(r["area"], 0) + 1

        if area_list:
            del_area = st.selectbox("削除するエリア", area_list, key="del_area")
            st.warning(
                f"**{del_area}** のデータ **{area_counts.get(del_area, 0)} 件** を削除します。"
                f"この操作は取り消せません。"
            )

            col_confirm, col_btn = st.columns([2, 1])
            with col_confirm:
                confirm_text = st.text_input(
                    "確認のためエリア名を入力してください",
                    key="del_confirm",
                    placeholder=del_area,
                )
            with col_btn:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("削除実行", type="primary", key="del_btn"):
                    if confirm_text == del_area:
                        db_del.table("hotels").delete().eq("area", del_area).execute()
                        st.success(f"**{del_area}** のデータを削除しました。")
                        st.rerun()
                    else:
                        st.error("エリア名が一致しません。")
        else:
            st.info("データがありません。")
    else:
        st.info("データがありません。")
