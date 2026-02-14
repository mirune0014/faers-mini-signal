import os
import sys
from datetime import date, datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import streamlit as st

# Ensure source packages are importable in all environments:
#   - PyInstaller bundle: sys._MEIPASS contains everything
#   - Repo / editable install: add src/ to sys.path
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _meipass = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    if str(_meipass) not in sys.path:
        sys.path.insert(0, str(_meipass))
else:
    _REPO_ROOT = Path(__file__).resolve().parents[1]
    _SRC_DIR = _REPO_ROOT / "src"
    if str(_SRC_DIR) not in sys.path:
        sys.path.insert(0, str(_SRC_DIR))

from faers_signal import _resources
from faers_signal.metrics import (
    ABCD,
    prr,
    chi_square_1df,
    ror,
    ror_ci95,
    ic_simple,
    ic_simple_ci95,
)


st.set_page_config(page_title="FAERS Mini Signal", layout="wide")
st.title("FAERS Mini Signal")

db_path = Path(os.environ.get("FAERS_DB", "data/faers.duckdb"))

# ── Sidebar: Filters ─────────────────────────────────────────────
st.sidebar.header("フィルタ")
st.sidebar.caption(f"DB: `{db_path.name}`")

suspect_only = st.sidebar.checkbox("被疑薬のみ (role=1)", value=True)
min_a = st.sidebar.number_input("最小A件数", min_value=0, value=3, step=1)
drug_filter = st.sidebar.text_input("薬剤名 (前方一致)", value="")
pt_filter = st.sidebar.text_input("副作用PT (前方一致)", value="")

# ── Sidebar: Data download ───────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.header("📥 openFDA データ取得")

dl_drug = st.sidebar.text_input("薬剤名フィルタ", value="", key="dl_drug",
                                 help="例: aspirin, metformin")
dl_col1, dl_col2 = st.sidebar.columns(2)
with dl_col1:
    dl_since = st.date_input("開始日", value=date(2023, 1, 1), key="dl_since")
with dl_col2:
    dl_until = st.date_input("終了日", value=date.today(), key="dl_until")
dl_max = st.sidebar.number_input("最大取得件数", min_value=100, max_value=26000,
                                  value=5000, step=1000)

if st.sidebar.button("🔄 openFDA から取得", use_container_width=True):
    with st.spinner("openFDA API からデータを取得中..."):
        from faers_signal.download_openfda import fetch_and_ingest

        progress_bar = st.sidebar.progress(0)
        status_text = st.sidebar.empty()

        def _on_progress(fetched: int, target: int) -> None:
            pct = min(1.0, fetched / target)
            progress_bar.progress(pct)
            status_text.text(f"{fetched:,} / {target:,} 件")

        try:
            dl_con = duckdb.connect(str(db_path))
            # Ensure schema exists
            dl_con.execute(_resources.get_sql("schema.sql"))

            total = fetch_and_ingest(
                dl_con,
                drug=dl_drug if dl_drug else None,
                since=dl_since.strftime("%Y-%m-%d") if dl_since else None,
                until=dl_until.strftime("%Y-%m-%d") if dl_until else None,
                max_records=dl_max,
                progress_callback=_on_progress,
            )
            dl_con.close()
            progress_bar.progress(1.0)
            st.sidebar.success(f"✅ {total:,} 件取得完了！")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"エラー: {e}")

# ── Main: Metrics table ──────────────────────────────────────────
con = duckdb.connect(str(db_path))
sql = _resources.get_sql("abcd.sql")
if not suspect_only:
    sql = sql.replace("FROM drugs WHERE role = 1", "FROM drugs WHERE role in (1,2,3)")

df = con.execute(sql).fetch_df()

# Show DB stats
report_count = con.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
drug_count = con.execute("SELECT COUNT(DISTINCT drug_name) FROM drugs").fetchone()[0]
pt_count = con.execute("SELECT COUNT(DISTINCT meddra_pt) FROM reactions").fetchone()[0]
con.close()

col1, col2, col3 = st.columns(3)
col1.metric("レポート数", f"{report_count:,}")
col2.metric("薬剤数", f"{drug_count:,}")
col3.metric("副作用PT数", f"{pt_count:,}")

if not df.empty:
    if drug_filter:
        df = df[df["drug"].str.startswith(drug_filter.lower())]
    if pt_filter:
        df = df[df["pt"].str.startswith(pt_filter.lower())]

if not df.empty:
    def _metrics_row(row: pd.Series):
        ab = ABCD(int(row.A), int(row.B), int(row.C), int(row.D), int(row.total_reports))
        prr_v = prr(ab)
        chi = chi_square_1df(ab)
        ror_v = ror(ab)
        ror_l, ror_u = ror_ci95(ab)
        ic_v = ic_simple(ab)
        ic_l, ic_u = ic_simple_ci95(ab)
        return pd.Series(
            {
                "PRR": prr_v,
                "Chi2_1df": chi,
                "ROR": ror_v,
                "ROR_CI_L": ror_l,
                "ROR_CI_U": ror_u,
                "IC": ic_v,
                "IC_CI_L": ic_l,
                "IC_CI_U": ic_u,
            }
        )

    metrics_df = df.apply(_metrics_row, axis=1)
    mdf = pd.concat([df.reset_index(drop=True), metrics_df.reset_index(drop=True)], axis=1)
    mdf = mdf[mdf["A"] >= min_a]
else:
    mdf = df

st.subheader("シグナル検出結果")
st.dataframe(mdf, use_container_width=True)

csv = mdf.to_csv(index=False).encode("utf-8") if not mdf.empty else b""
st.download_button("📄 CSV ダウンロード", data=csv, file_name="metrics.csv", mime="text/csv")
