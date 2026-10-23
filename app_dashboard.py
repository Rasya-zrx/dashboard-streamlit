import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path


def format_id_number(value, decimals=0):
    """Format angka: titik untuk ribuan dan koma untuk desimal."""
    if pd.isna(value):
        return "—"

    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


st.set_page_config(page_title="Foodpanda Analytics Dashboard", page_icon="🍔", layout="wide")

# Minimal, restrained styling that keeps the dashboard readable.

st.markdown("""
<style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    /* KPI cards: readable in both light and dark mode */
    div[data-testid="stMetric"] {
        background-color: rgba(128, 128, 128, 0.12);
        border: 1px solid rgba(128, 128, 128, 0.35);
        padding: 16px;
        border-radius: 10px;
    }

    /* Follow the text color of the active Streamlit theme */
    div[data-testid="stMetric"] label,
    div[data-testid="stMetric"] [data-testid="stMetricLabel"],
    div[data-testid="stMetric"] [data-testid="stMetricValue"],
    div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
        color: inherit !important;
    }

    div[data-testid="stMetricLabel"] {
        font-size: 0.9rem;
    }

    h1, h2, h3 {
        letter-spacing: -0.02em;
    }
</style>
""", unsafe_allow_html=True)


st.title("🍔 Foodpanda Analytics Dashboard")
st.caption("Dashboard interaktif untuk melihat pola pesanan, estimasi penjualan, rating pelanggan, dan status pengiriman di Pakistan.")

DATA_PATH = Path(__file__).with_name("Foodpanda Analysis Dataset.csv")

@st.cache_data

def load_data(file_path):
    data = pd.read_csv(file_path)
    # Parse dates safely; the source uses date strings such as M/D/YYYY.
    for col in ["signup_date", "order_date", "last_order_date", "rating_date"]:
        if col in data.columns:
            data[col] = pd.to_datetime(data[col], errors="coerce")
    for col in ["quantity", "price", "rating", "order_frequency", "loyalty_points"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    # Standardize whitespace without changing the meaning of categories.
    for col in data.select_dtypes(include="object").columns:
        data[col] = data[col].str.strip()
    data["estimated_sales"] = data["price"] * data["quantity"]
    data["order_month"] = data["order_date"].dt.to_period("M").dt.to_timestamp()
    return data

try:
    df = load_data(DATA_PATH)
except FileNotFoundError:
    st.error("File dataset tidak ditemukan. Simpan 'Foodpanda Analysis Dataset.csv' di folder yang sama dengan app.py.")
    st.stop()

# Sidebar filters
st.sidebar.header("Filter Dashboard")
valid_dates = df["order_date"].dropna()
if valid_dates.empty:
    st.error("Kolom order_date tidak memiliki tanggal yang valid.")
    st.stop()
min_date, max_date = valid_dates.min().date(), valid_dates.max().date()
date_range = st.sidebar.date_input("Rentang tanggal pesanan", value=(min_date, max_date), min_value=min_date, max_value=max_date)
if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = end_date = date_range

cities = sorted(df["city"].dropna().unique().tolist())
selected_cities = st.sidebar.multiselect("Kota", cities, default=cities)
categories = sorted(df["category"].dropna().unique().tolist())
selected_categories = st.sidebar.multiselect("Kategori makanan", categories, default=categories)
statuses = sorted(df["delivery_status"].dropna().unique().tolist())
selected_statuses = st.sidebar.multiselect("Status pengiriman", statuses, default=statuses)

filtered = df[
    df["order_date"].dt.date.between(start_date, end_date)
    & df["city"].isin(selected_cities)
    & df["category"].isin(selected_categories)
    & df["delivery_status"].isin(selected_statuses)
].copy()

if filtered.empty:
    st.warning("Tidak ada data yang cocok dengan filter yang dipilih. Ubah atau hapus sebagian filter.")
    st.stop()

# KPIs
n_orders = filtered["order_id"].nunique()
estimated_sales = filtered["estimated_sales"].sum(min_count=1)
avg_rating = filtered["rating"].mean()
delivered_pct = filtered["delivery_status"].eq("Delivered").mean() * 100
k1, k2, k3, k4 = st.columns(4)

k1.metric("Total Pesanan", format_id_number(n_orders, 0))
k2.metric(
    "Estimasi Nilai Penjualan",
    f"{format_id_number(estimated_sales, 0)}"
)
k3.metric(
    "Rata-rata Rating",
    f"{format_id_number(avg_rating, 2)} / 5"
    if pd.notna(avg_rating)
    else "Belum tersedia"
)
k4.metric("Pesanan Terkirim", f"{format_id_number(delivered_pct, 1)}%")


st.divider()

# Chart 1: monthly trend (line chart)

st.subheader("Tren Pendapatan Per Bulan")

monthly = filtered.groupby("order_month", as_index=False).agg(
    estimated_sales=("estimated_sales", "sum")
).sort_values("order_month")

fig_line = px.line(
    monthly,
    x="order_month",
    y="estimated_sales",
    markers=True,
    labels={
        "order_month": "Bulan",
        "estimated_sales": "Pendapatan"
    }
)
fig_line.update_layout(
    margin=dict(l=10, r=10, t=25, b=10),
    xaxis_title=None,
    yaxis_title="Pendapatan"
)
st.plotly_chart(fig_line, use_container_width=True)


left, right = st.columns(2)
with left:
    # Chart 2: bar chart
    st.subheader("Pendapatan per Kategori")
    by_category = filtered.groupby("category", as_index=False)["estimated_sales"].sum().sort_values("estimated_sales", ascending=False)
    fig_bar = px.bar(by_category, x="category", y="estimated_sales", text_auto=".2s",
                     labels={"category": "Kategori", "estimated_sales": "Pendapatan"})
    fig_bar.update_layout(margin=dict(l=10, r=10, t=25, b=10), xaxis_title=None, yaxis_title="Pendapatan")
    st.plotly_chart(fig_bar, use_container_width=True)
    
with right:
    # Chart 3: pie chart
    st.subheader("Komposisi Status Pengiriman")
    status_counts = filtered["delivery_status"].value_counts().rename_axis("delivery_status").reset_index(name="orders")
    fig_pie = px.pie(status_counts, names="delivery_status", values="orders", hole=0.42,
                     labels={"delivery_status": "Status", "orders": "Jumlah pesanan"})
    fig_pie.update_layout(margin=dict(l=10, r=10, t=25, b=10), legend_title_text="Status")
    st.plotly_chart(fig_pie, use_container_width=True)

left2, right2 = st.columns(2)
with left2:
    # Chart 4: histogram
    st.subheader("Distribusi Rating")
    rating_data = filtered["rating"].dropna()
    if not rating_data.empty:
        fig_hist = px.histogram(rating_data.to_frame(name="rating"), x="rating", nbins=5,
                                labels={"rating": "Rating (1–5)", "count": "Jumlah rating"})
        fig_hist.update_layout(margin=dict(l=10, r=10, t=25, b=10), xaxis_title="Rating", yaxis_title="Jumlah")
        st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("Tidak ada rating yang terisi pada kombinasi filter ini.")
with right2:
    # Additional chart: bar chart by city

    # Chart: bar chart horizontal berdasarkan kota
    st.subheader("Jumlah Pesanan per Kota")

    by_city = (
        filtered.groupby("city", as_index=False)
        .agg(total_orders=("order_id", "nunique"))
        .sort_values("total_orders", ascending=True)
    )

    fig_city = px.bar(
        by_city,
        x="total_orders",
        y="city",
        orientation="h",
        text="total_orders",
        labels={
            "city": "Kota",
            "total_orders": "Jumlah pesanan"
        }
    )

    fig_city.update_traces(textposition="outside")
    fig_city.update_layout(
        margin=dict(l=10, r=35, t=25, b=10),
        xaxis_title="Jumlah pesanan",
        yaxis_title=None,
        yaxis={"categoryorder": "total ascending"}
    )

    st.plotly_chart(fig_city, use_container_width=True)


st.divider()
st.subheader("Rincian Pesanan")
show_cols = ["order_id", "order_date", "city", "restaurant_name", "dish_name", "category", "quantity", "price", "estimated_sales", "payment_method", "delivery_status", "rating"]
show_cols = [c for c in show_cols if c in filtered.columns]
st.dataframe(filtered[show_cols].sort_values("order_date", ascending=False), use_container_width=True, hide_index=True)

csv = filtered[show_cols].to_csv(index=False).encode("utf-8-sig")
st.download_button("Unduh data hasil filter (CSV)", data=csv, file_name="foodpanda_data_filtered.csv", mime="text/csv")

