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
    signal_flags,
    classify_signal,
)
from faers_signal.analysis_spec import AnalysisSpec, Manifest


st.set_page_config(page_title="FAERS Mini Signal", layout="wide")
st.title("FAERS Mini Signal")

db_path = Path(os.environ.get("FAERS_DB", "data/faers.duckdb"))

# repo ルート基準でDBを選ぶ（Cloudデモは sample を優先）
REPO_ROOT = Path(__file__).resolve().parents[1]
default_db = REPO_ROOT / "data" / "sample.duckdb"
if not default_db.exists():
    default_db = REPO_ROOT / "data" / "faers.duckdb"

db_path = Path(os.environ.get("FAERS_DB", str(default_db)))
db_path.parent.mkdir(parents=True, exist_ok=True)

# ── Sidebar: Filters ─────────────────────────────────────────────
st.sidebar.header("フィルタ")
st.sidebar.caption(f"DB: `{db_path.name}`")

suspect_only = st.sidebar.checkbox("被疑薬のみ (role=1)", value=True)
min_a = st.sidebar.number_input("最小A件数", min_value=0, value=3, step=1)
drug_filter = st.sidebar.text_input("薬剤名 (前方一致)", value="")
pt_filter = st.sidebar.text_input("副作用PT (前方一致)", value="")

# ── Sidebar: Signal mode ─────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.header("🔬 シグナル判定")
SIGNAL_MODES = {
    "Sensitive（探索）": "sensitive",
    "Balanced（推奨）": "balanced",
    "Specific（精度重視）": "specific",
}
signal_mode_label = st.sidebar.selectbox(
    "判定モード",
    list(SIGNAL_MODES.keys()),
    index=1,
    help=(
        "Sensitive: 3基準のいずれか1つ\n"
        "Balanced: 3基準のうち2つ以上（推奨）\n"
        "Specific: 3基準すべて"
    ),
)
signal_mode = SIGNAL_MODES[signal_mode_label]

# ── Sidebar: Ranking ─────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.header("📊 ランキング / 可視化")
RANKING_OPTIONS = {
    "IC025 降順（頑健）": "ic025",
    "報告件数A 降順": "a_desc",
    "バランス (IC025 × log(1+A))": "balance_score",
}
ranking_label = st.sidebar.selectbox(
    "ランキング基準",
    list(RANKING_OPTIONS.keys()),
    index=0,
    help="可視化のTopN選択およびソートに使用",
)
ranking_criterion = RANKING_OPTIONS[ranking_label]
top_n = st.sidebar.number_input("TopN", min_value=5, max_value=50, value=15, step=5)

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

# ★重要：空DBでも落ちないようにスキーマを作る
con.execute(_resources.get_sql("schema.sql"))

# 先に件数チェック（0なら abcd.sql を走らせない）
report_count = con.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
if report_count == 0:
    st.info("DBにデータがありません。左の「openFDA から取得」を実行するか、FAERS_DB で既存DBを指定してください。")
    con.close()
    st.stop()

sql = _resources.get_sql("abcd.sql")
if not suspect_only:
    sql = sql.replace("FROM drugs WHERE role = 1", "FROM drugs WHERE role in (1,2,3)")

df = con.execute(sql).fetch_df()

# Show DB stats
drug_count = con.execute("SELECT COUNT(DISTINCT drug_name) FROM drugs").fetchone()[0]
pt_count = con.execute("SELECT COUNT(DISTINCT meddra_pt) FROM reactions").fetchone()[0]

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

        # Signal detection with explicit flags
        flags = signal_flags(ab, min_a=int(min_a))
        is_signal = classify_signal(flags, mode=signal_mode)

        return pd.Series(
            {
                "PRR": round(prr_v, 2) if not np.isnan(prr_v) else np.nan,
                "Chi2": round(chi, 2) if not np.isnan(chi) else np.nan,
                "ROR": round(ror_v, 2) if not np.isnan(ror_v) else np.nan,
                "ROR_lo": round(ror_l, 2) if not np.isnan(ror_l) else np.nan,
                "ROR_hi": round(ror_u, 2) if not np.isnan(ror_u) else np.nan,
                "IC": round(ic_v, 3) if not np.isnan(ic_v) else np.nan,
                "IC_lo": round(ic_l, 3) if not np.isnan(ic_l) else np.nan,
                "IC_hi": round(ic_u, 3) if not np.isnan(ic_u) else np.nan,
                "flag_evans": flags["flag_evans"],
                "flag_ror025": flags["flag_ror025"],
                "flag_ic025": flags["flag_ic025"],
                "Signal": "⚠️" if is_signal else "",
            }
        )

    metrics_df = df.apply(_metrics_row, axis=1)
    mdf = pd.concat([df.reset_index(drop=True), metrics_df.reset_index(drop=True)], axis=1)
    mdf = mdf[mdf["A"] >= min_a]
else:
    mdf = df

# ── Ranking score computation ────────────────────────────────────
def _compute_rank_score(mdf: pd.DataFrame, criterion: str) -> pd.DataFrame:
    """Add a _rank_score column for TopN selection."""
    if criterion == "ic025":
        mdf["_rank_score"] = mdf["IC_lo"].fillna(-999)
    elif criterion == "a_desc":
        mdf["_rank_score"] = mdf["A"].astype(float)
    elif criterion == "balance_score":
        ic025_clipped = mdf["IC_lo"].fillna(0).clip(lower=0)
        mdf["_rank_score"] = ic025_clipped * np.log1p(mdf["A"].astype(float))
    else:
        mdf["_rank_score"] = mdf["IC_lo"].fillna(-999)
    return mdf

if not mdf.empty and "IC_lo" in mdf.columns:
    mdf = _compute_rank_score(mdf, ranking_criterion)

# ── Signal filter toggle ─────────────────────────────────────────
st.subheader("シグナル検出結果")

# Analysis provenance info
st.caption(
    f"判定モード: **{signal_mode_label}** | "
    f"ランキング: **{ranking_label}** | "
    f"TopN: **{top_n}**"
)

if not mdf.empty and "Signal" in mdf.columns:
    signal_only = st.checkbox("⚠️ シグナル検出のみ表示", value=False)
    if signal_only:
        mdf = mdf[mdf["Signal"] == "⚠️"]

    sig_count = (mdf["Signal"] == "⚠️").sum()
    st.caption(f"表示行数: {len(mdf):,}  |  シグナル検出: {sig_count:,} 件")

# ── Color-coded table ────────────────────────────────────────────
def _highlight_signal(row):
    if row.get("Signal") == "⚠️":
        return ["background-color: rgba(255, 200, 200, 0.3)"] * len(row)
    return [""] * len(row)

# Display columns (hide internal columns)
_HIDE_COLS = {"_rank_score"}

if not mdf.empty:
    display_cols = [c for c in mdf.columns if c not in _HIDE_COLS]
    styled = mdf[display_cols].style.apply(_highlight_signal, axis=1).format(
        {c: "{:.2f}" for c in ["PRR", "Chi2", "ROR", "ROR_lo", "ROR_hi"]
         if c in mdf.columns},
        na_rep="—",
    )
    st.dataframe(styled, use_container_width=True)
else:
    st.dataframe(mdf, use_container_width=True)

# ── Downloads: CSV + Manifest ────────────────────────────────────
if not mdf.empty:
    dl_cols = [c for c in mdf.columns if c not in _HIDE_COLS]
    csv = mdf[dl_cols].to_csv(index=False).encode("utf-8")
else:
    csv = b""

# Build manifest
_spec = AnalysisSpec(
    suspect_only=suspect_only,
    min_a=int(min_a),
    drug_filter=drug_filter or None,
    pt_filter=pt_filter or None,
    signal_mode=signal_mode,
    ranking_criterion=ranking_criterion,
    top_n=int(top_n),
)
_manifest = Manifest(spec=_spec)
_manifest.populate_env()
_manifest.total_reports = report_count
_manifest.total_drugs = drug_count
_manifest.total_reactions = pt_count
_manifest.total_pairs = len(mdf) if not mdf.empty else 0
_manifest.signal_count = int((mdf["Signal"] == "⚠️").sum()) if not mdf.empty and "Signal" in mdf.columns else 0

dl_c1, dl_c2 = st.columns(2)
with dl_c1:
    st.download_button("📄 CSV ダウンロード", data=csv, file_name="metrics.csv", mime="text/csv")
with dl_c2:
    manifest_json = _manifest.to_json().encode("utf-8")
    st.download_button(
        "📋 Manifest (JSON)",
        data=manifest_json,
        file_name="metrics.manifest.json",
        mime="application/json",
    )

# ── Note on analysis unit ────────────────────────────────────────
st.caption(
    "⚠️ 注意: FAERS の1報告に複数の薬剤・副作用が含まれますが、特定の薬剤と特定の副作用の"
    "直接的な紐づけはできません。シグナルは仮説生成のためのものであり、因果関係を示すものではありません。"
)

# ── Visualization ────────────────────────────────────────────────
if not mdf.empty and "PRR" in mdf.columns:
    import altair as alt
    from scipy.stats import chi2 as _chi2_dist

    st.subheader("📊 可視化")
    chart_type = st.selectbox(
        "グラフ種類",
        ["Volcano Plot", "バブルチャート", "ヒートマップ"],
    )

    # Prepare viz dataframe (drop NaN/inf rows for charting)
    vdf = mdf.dropna(subset=["PRR", "Chi2"]).copy()
    # Guard: remove infinite or extreme values that distort charts
    vdf = vdf[np.isfinite(vdf["PRR"]) & np.isfinite(vdf["Chi2"])]
    vdf = vdf[(vdf["PRR"] > 0) & (vdf["PRR"] < 1e6)]  # remove extreme outliers
    if vdf.empty:
        st.warning("可視化に必要なデータがありません。")
    else:
        vdf["log2_PRR"] = np.log2(vdf["PRR"].clip(lower=1e-10))
        vdf["IC025"] = vdf["IC_lo"].fillna(0)
        vdf["label"] = vdf["drug"] + " + " + vdf["pt"]

        # ── TopN selection using unified ranking ──
        def _get_top_items(vdf: pd.DataFrame, col: str, n: int) -> list:
            """Get top-N unique items from *col* based on _rank_score."""
            ranked = vdf.groupby(col)["_rank_score"].max().nlargest(n)
            return ranked.index.tolist()

        if chart_type == "Volcano Plot":
            # Mode A (PV-aligned): X = log₂(PRR), Y = IC025
            volcano = (
                alt.Chart(vdf)
                .mark_circle(size=60, opacity=0.7)
                .encode(
                    x=alt.X("log2_PRR:Q", title="log₂(PRR)"),
                    y=alt.Y("IC025:Q", title="IC₀₂₅（IC 下限 95%CI）"),
                    color=alt.condition(
                        alt.datum.Signal == "⚠️",
                        alt.value("#e74c3c"),
                        alt.value("#95a5a6"),
                    ),
                    tooltip=["label", "A", "PRR", "ROR", "IC", "IC_lo", "Signal",
                             "flag_evans", "flag_ror025", "flag_ic025"],
                )
                .properties(width="container", height=450)
                .interactive()
            )
            # Threshold lines
            prr_line = alt.Chart(pd.DataFrame({"x": [1.0]})).mark_rule(
                strokeDash=[4, 4], color="orange"
            ).encode(x="x:Q")
            ic025_line = alt.Chart(pd.DataFrame({"y": [0.0]})).mark_rule(
                strokeDash=[4, 4], color="orange"
            ).encode(y="y:Q")

            st.altair_chart(volcano + prr_line + ic025_line, use_container_width=True)
            st.caption(
                "X: log₂(PRR)、Y: IC₀₂₅（IC下限95%CI）。"
                "オレンジ線: PRR=2 (縦), IC₀₂₅=0 (横)。赤点=シグナル検出"
            )

        elif chart_type == "バブルチャート":
            top_drugs = _get_top_items(vdf, "drug", int(top_n))
            bdf = vdf[vdf["drug"].isin(top_drugs)]

            bubble = (
                alt.Chart(bdf)
                .mark_circle(opacity=0.7)
                .encode(
                    x=alt.X("drug:N", title="薬剤名", sort="-y"),
                    y=alt.Y("PRR:Q", title="PRR"),
                    size=alt.Size("A:Q", title="報告件数A", scale=alt.Scale(range=[30, 500])),
                    color=alt.condition(
                        alt.datum.Signal == "⚠️",
                        alt.value("#e74c3c"),
                        alt.value("#3498db"),
                    ),
                    tooltip=["drug", "pt", "A", "PRR", "ROR", "IC", "IC_lo", "Signal",
                             "flag_evans", "flag_ror025", "flag_ic025"],
                )
                .properties(width="container", height=450)
            )
            st.altair_chart(bubble, use_container_width=True)
            st.caption(f"Top {top_n} 薬剤（{ranking_label}）。バブルサイズ=報告件数A、赤=シグナル検出")

        elif chart_type == "ヒートマップ":
            top_drugs = _get_top_items(vdf, "drug", int(top_n))
            top_pts = _get_top_items(vdf, "pt", int(top_n))
            hdf = vdf[(vdf["drug"].isin(top_drugs)) & (vdf["pt"].isin(top_pts))]

            # Color metric selector
            HEAT_COLOR_OPTIONS = {
                "IC₀₂₅（推奨）": "IC025",
                "IC（点推定）": "IC",
                "PRR": "PRR",
            }
            heat_color_label = st.selectbox(
                "色指標", list(HEAT_COLOR_OPTIONS.keys()), index=0,
            )
            heat_color_col = HEAT_COLOR_OPTIONS[heat_color_label]

            # Ensure the color column exists
            if heat_color_col == "IC025":
                hdf = hdf.copy()
                hdf["IC025"] = hdf["IC_lo"].fillna(0)

            heatmap = (
                alt.Chart(hdf)
                .mark_rect()
                .encode(
                    x=alt.X("pt:N", title="副作用PT"),
                    y=alt.Y("drug:N", title="薬剤名"),
                    color=alt.Color(
                        f"{heat_color_col}:Q",
                        title=heat_color_label,
                        scale=alt.Scale(scheme="redblue", domainMid=0, reverse=True),
                    ),
                    tooltip=["drug", "pt", "A", "PRR", "ROR", "IC", "IC_lo",
                             "Signal", "flag_evans", "flag_ror025", "flag_ic025"],
                )
                .properties(width="container", height=450)
            )
            # A count annotation on cells
            text = (
                alt.Chart(hdf)
                .mark_text(fontSize=9, color="black")
                .encode(
                    x=alt.X("pt:N"),
                    y=alt.Y("drug:N"),
                    text=alt.Text("A:Q"),
                )
            )

            st.altair_chart(heatmap + text, use_container_width=True)
            st.caption(
                f"Top {top_n} 薬剤 × Top {top_n} PT（{ranking_label}）。"
                f"色={heat_color_label}、セル内数字=報告件数A"
            )


