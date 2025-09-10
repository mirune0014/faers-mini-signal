import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import streamlit as st

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
st.sidebar.header("Filters")
st.sidebar.write(f"DB: {db_path}")

suspect_only = st.sidebar.checkbox("Suspect drugs only (role=1)", value=True)
min_a = st.sidebar.number_input("Min A count", min_value=0, value=3, step=1)
drug_filter = st.sidebar.text_input("Drug startswith", value="")
pt_filter = st.sidebar.text_input("PT startswith", value="")

con = duckdb.connect(str(db_path))
sql = (Path(__file__).parents[1] / "src" / "faers_signal" / "abcd.sql").read_text(encoding="utf-8")
if not suspect_only:
    sql = sql.replace("FROM drugs WHERE role = 1", "FROM drugs WHERE role in (1,2,3)")

df = con.execute(sql).fetch_df()

if not df.empty:
    if drug_filter:
        df = df[df["drug"].str.startswith(drug_filter.lower())]
    if pt_filter:
        df = df[df["pt"].str.startswith(pt_filter.lower())]

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

    mdf = df.join(df.apply(_metrics_row, axis=1))
    mdf = mdf[mdf["A"] >= min_a]
else:
    mdf = df

st.subheader("Metrics")
st.dataframe(mdf, use_container_width=True)

csv = mdf.to_csv(index=False).encode("utf-8") if not mdf.empty else b""
st.download_button("Download CSV", data=csv, file_name="metrics.csv", mime="text/csv")

