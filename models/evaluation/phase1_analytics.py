"""
Phase 1 Analytics Functions
============================
Extracted from notebook Phase 1 (cells 2-19).
Clean, working business-analytics functions that ran successfully
on synthetic sales data. These are the only truly "clean and working"
cells from the notebook as identified in the audit.

Functions:
- create_sample_sales_data    — synthetic sales dataset generator
- clean_data                  — dedup, dropna, time-feature extraction, outlier removal
- calculate_key_metrics       — revenue/customer KPI summary
- create_visualizations       — 4-panel matplotlib/seaborn charts
- ai_insights                 — trend, anomaly, best-performer summary (sklearn)
- advanced_sales_forecast     — Holt-Winters time-series forecast (statsmodels)
- ai_customer_segmentation    — KMeans 4-segment customer clustering
- ml_anomaly_detection        — IsolationForest unsupervised anomaly detection
- create_master_dashboard     — composite 9-panel dashboard figure
- export_for_powerbi          — CSV export (Colab download call stripped)
- generate_report             — executive text summary

All ``google.colab`` imports and ``%pip`` magic expressions have been removed.
"""

from __future__ import annotations

import warnings
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Optional visualisation
try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    sns.set_style("whitegrid")
    plt.rcParams["figure.figsize"] = (12, 6)
    HAS_VIZ = True
except ImportError:
    plt = None  # type: ignore[assignment]
    sns = None  # type: ignore[assignment]
    HAS_VIZ = False

# Optional ML / stats
try:
    from sklearn.cluster import KMeans
    from sklearn.ensemble import IsolationForest
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    from sklearn.metrics import mean_absolute_error
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False


# ============================================================================
# DATA GENERATION
# ============================================================================

def create_sample_sales_data(num_records: int = 1_000, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic sales data covering ~1 year."""
    np.random.seed(seed)
    start_date = datetime(2024, 1, 1)
    dates = [start_date + timedelta(days=x) for x in range(365)]

    products = ["Laptop", "Phone", "Tablet", "Monitor", "Keyboard", "Mouse", "Headphones"]
    regions = ["North", "South", "East", "West", "Central"]

    data = {
        "Date": np.random.choice(dates, num_records),
        "Product": np.random.choice(products, num_records),
        "Region": np.random.choice(regions, num_records),
        "Units_Sold": np.random.randint(1, 50, num_records),
        "Unit_Price": np.random.randint(50, 2_000, num_records),
        "Customer_ID": [
            f"CUST{str(i).zfill(5)}" for i in np.random.randint(1_000, 9_999, num_records)
        ],
    }
    df = pd.DataFrame(data)
    df["Total_Sales"] = df["Units_Sold"] * df["Unit_Price"]
    return df.sort_values("Date").reset_index(drop=True)


# ============================================================================
# CLEANING
# ============================================================================

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Dedup, handle missing values, add time columns, remove outliers (3σ)."""
    df_clean = df.copy()

    before = len(df_clean)
    df_clean = df_clean.drop_duplicates()
    print(f"[clean] Removed {before - len(df_clean)} duplicates")

    before = df_clean.isnull().sum().sum()
    df_clean = df_clean.dropna()
    print(f"[clean] Handled {before} missing values")

    df_clean["Date"] = pd.to_datetime(df_clean["Date"])
    df_clean["Year"] = df_clean["Date"].dt.year
    df_clean["Month"] = df_clean["Date"].dt.month
    df_clean["Month_Name"] = df_clean["Date"].dt.strftime("%B")
    df_clean["Quarter"] = df_clean["Date"].dt.quarter
    df_clean["Day_of_Week"] = df_clean["Date"].dt.day_name()

    mean_s = df_clean["Total_Sales"].mean()
    std_s = df_clean["Total_Sales"].std()
    before = len(df_clean)
    df_clean = df_clean[df_clean["Total_Sales"] <= mean_s + 3 * std_s]
    print(f"[clean] Removed {before - len(df_clean)} outliers (>3σ)")
    print(f"[clean] Final dataset: {len(df_clean)} records")

    return df_clean


# ============================================================================
# KEY METRICS
# ============================================================================

def calculate_key_metrics(df: pd.DataFrame, verbose: bool = True) -> dict:
    """Return a dict of KPIs and optionally print the dashboard."""
    total_revenue = df["Total_Sales"].sum()
    total_units = df["Units_Sold"].sum()
    total_transactions = len(df)  # noqa: F841  (kept for reporting parity with notebook)
    avg_transaction = df["Total_Sales"].mean()
    unique_customers = df["Customer_ID"].nunique()

    top_products = df.groupby("Product")["Total_Sales"].sum().sort_values(ascending=False)
    top_regions = df.groupby("Region")["Total_Sales"].sum().sort_values(ascending=False)

    if verbose:
        print("\n=== BUSINESS METRICS DASHBOARD ===")
        print(f"  Total Revenue:      ${total_revenue:,.2f}")
        print(f"  Avg Transaction:    ${avg_transaction:,.2f}")
        print(f"  Total Units Sold:   {total_units:,}")
        print(f"  Unique Customers:   {unique_customers:,}")
        print("\n  Top 5 Products:")
        for i, (prod, sales) in enumerate(top_products.head(5).items(), 1):
            print(f"    {i}. {prod}: ${sales:,.2f}")
        print("\n  Top Regions:")
        for i, (reg, sales) in enumerate(top_regions.items(), 1):
            print(f"    {i}. {reg}: ${sales:,.2f}")

    return {
        "total_revenue": float(total_revenue),
        "total_units": int(total_units),
        "avg_transaction": float(avg_transaction),
        "unique_customers": int(unique_customers),
        "top_products": top_products.to_dict(),
        "top_regions": top_regions.to_dict(),
    }


# ============================================================================
# VISUALISATIONS
# ============================================================================

def create_visualizations(df: pd.DataFrame) -> None:
    """4-panel chart: bar (product), pie (region), line (monthly), heatmap."""
    if not HAS_VIZ:
        print("[skip] matplotlib/seaborn not installed")
        return

    # 1. Revenue by product
    plt.figure(figsize=(12, 6))
    product_sales = df.groupby("Product")["Total_Sales"].sum().sort_values()
    product_sales.plot(kind="barh", color="steelblue")
    plt.title("Total Revenue by Product", fontsize=16, fontweight="bold")
    plt.xlabel("Revenue ($)")
    plt.tight_layout()
    plt.show()

    # 2. Revenue by region (pie)
    plt.figure(figsize=(10, 6))
    region_sales = df.groupby("Region")["Total_Sales"].sum()
    plt.pie(region_sales, labels=region_sales.index, autopct="%1.1f%%", startangle=90)
    plt.title("Revenue Distribution by Region", fontsize=16, fontweight="bold")
    plt.axis("equal")
    plt.tight_layout()
    plt.show()

    # 3. Monthly revenue trend
    plt.figure(figsize=(14, 6))
    monthly = df.groupby("Month")["Total_Sales"].sum()
    plt.plot(monthly.index, monthly.values, marker="o", linewidth=2, markersize=8, color="green")
    plt.title("Monthly Sales Trend", fontsize=16, fontweight="bold")
    plt.xlabel("Month")
    plt.ylabel("Revenue ($)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

    # 4. Heatmap: day-of-week × product
    plt.figure(figsize=(12, 8))
    heatmap_data = df.pivot_table(
        values="Total_Sales", index="Day_of_Week", columns="Product", aggfunc="sum"
    )
    sns.heatmap(heatmap_data, annot=True, fmt=".0f", cmap="YlOrRd", cbar_kws={"label": "Revenue ($)"})
    plt.title("Sales Heatmap: Day of Week vs Product", fontsize=16, fontweight="bold")
    plt.tight_layout()
    plt.show()


# ============================================================================
# AI INSIGHTS
# ============================================================================

def ai_insights(df: pd.DataFrame) -> dict:
    """Trend analysis, anomaly detection, best/worst performers."""
    if not HAS_SKLEARN:
        raise ImportError("scikit-learn is required: pip install scikit-learn")

    monthly_data = df.groupby("Month")["Total_Sales"].sum().reset_index()
    X = monthly_data["Month"].values.reshape(-1, 1)
    y = monthly_data["Total_Sales"].values

    model = LinearRegression()
    model.fit(X, y)
    trend = "increasing" if model.coef_[0] > 0 else "decreasing"
    trend_pct = abs(model.coef_[0] / y.mean() * 100)
    next_pred = float(model.predict([[len(monthly_data) + 1]])[0])

    mean_s = df["Total_Sales"].mean()
    std_s = df["Total_Sales"].std()
    anomalies = df[df["Total_Sales"] > mean_s + 2 * std_s]

    best_product = df.groupby("Product")["Total_Sales"].sum().idxmax()
    best_region = df.groupby("Region")["Total_Sales"].sum().idxmax()
    best_day = df.groupby("Day_of_Week")["Total_Sales"].sum().idxmax()
    worst_product = df.groupby("Product")["Total_Sales"].sum().idxmin()
    worst_region = df.groupby("Region")["Total_Sales"].sum().idxmin()
    worst_day = df.groupby("Day_of_Week")["Total_Sales"].sum().idxmin()

    print(f"  Sales are {trend} by ~{trend_pct:.1f}% per month")
    print(f"  Predicted next month: ${next_pred:,.2f}")
    print(f"  Anomalies (>2σ):      {len(anomalies)}")
    print(f"  Best product:  {best_product}  |  Worst: {worst_product}")
    print(f"  Best region:   {best_region}  |  Worst: {worst_region}")
    print(f"  Best day:      {best_day}      |  Worst: {worst_day}")

    return {
        "trend": trend,
        "trend_pct": trend_pct,
        "next_month_prediction": next_pred,
        "n_anomalies": len(anomalies),
        "best_product": best_product,
        "best_region": best_region,
        "best_day": best_day,
        "worst_product": worst_product,
        "worst_region": worst_region,
        "worst_day": worst_day,
    }


# ============================================================================
# FORECASTING
# ============================================================================

def advanced_sales_forecast(df: pd.DataFrame, periods: int = 6) -> pd.DataFrame:
    """Holt-Winters triple exponential smoothing forecast (statsmodels).

    Returns a DataFrame with columns: Month, Predicted_Sales, Confidence.
    """
    if not HAS_STATSMODELS:
        raise ImportError("statsmodels is required: pip install statsmodels")

    monthly_sales = df.groupby(df["Date"].dt.to_period("M"))["Total_Sales"].sum()
    monthly_sales.index = monthly_sales.index.to_timestamp()

    train_size = int(len(monthly_sales) * 0.8)
    train_data = monthly_sales[:train_size]
    test_data = monthly_sales[train_size:]

    fitted = ExponentialSmoothing(
        train_data, seasonal_periods=3, trend="add", seasonal="add"
    ).fit()
    test_pred = fitted.forecast(steps=len(test_data))
    mae = mean_absolute_error(test_data, test_pred)
    accuracy = 100 - (mae / test_data.mean() * 100)
    print(f"[forecast] Model accuracy: {accuracy:.1f}%  |  MAE: ${mae:,.2f}")

    # Retrain on full data for final forecast
    final_fitted = ExponentialSmoothing(
        monthly_sales, seasonal_periods=3, trend="add", seasonal="add"
    ).fit()
    forecast = final_fitted.forecast(steps=periods)

    last_date = monthly_sales.index[-1]
    future_dates = pd.date_range(
        start=last_date + pd.DateOffset(months=1), periods=periods, freq="MS"
    )

    forecast_df = pd.DataFrame(
        {
            "Month": future_dates.strftime("%B %Y"),
            "Predicted_Sales": forecast.values,
            "Confidence": ["High" if i < 3 else "Medium" for i in range(periods)],
        }
    )

    for _, row in forecast_df.iterrows():
        print(f"  {row['Month']}: ${row['Predicted_Sales']:,.2f}  ({row['Confidence']})")

    if HAS_VIZ:
        plt.figure(figsize=(14, 6))
        plt.plot(monthly_sales.index, monthly_sales.values, marker="o", label="Historical", color="blue")
        plt.plot(future_dates, forecast.values, marker="s", linestyle="--", label="Forecast", color="red")
        plt.fill_between(future_dates, forecast.values * 0.9, forecast.values * 1.1, alpha=0.2, color="red")
        plt.title("AI-Powered Sales Forecast", fontsize=16, fontweight="bold")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

    return forecast_df


# ============================================================================
# CUSTOMER SEGMENTATION
# ============================================================================

def ai_customer_segmentation(df: pd.DataFrame, n_clusters: int = 4) -> pd.DataFrame:
    """KMeans customer clustering. Returns augmented customer_metrics DataFrame."""
    if not HAS_SKLEARN:
        raise ImportError("scikit-learn is required")

    customer_metrics = df.groupby("Customer_ID").agg(
        Total_Revenue=("Total_Sales", "sum"),
        Avg_Order_Value=("Total_Sales", "mean"),
        Purchase_Frequency=("Total_Sales", "count"),
        Total_Units=("Units_Sold", "sum"),
        Product_Variety=("Product", "nunique"),
    ).reset_index()

    features = customer_metrics[
        ["Total_Revenue", "Avg_Order_Value", "Purchase_Frequency", "Product_Variety"]
    ]
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    customer_metrics["Segment"] = kmeans.fit_predict(features_scaled)

    segment_rank = (
        customer_metrics.groupby("Segment")["Total_Revenue"].mean().rank().astype(int).to_dict()
    )
    tier_names = {1: "Bronze", 2: "Silver", 3: "Gold", 4: "Platinum"}
    customer_metrics["Tier"] = customer_metrics["Segment"].map(
        lambda s: tier_names.get(segment_rank.get(s, 1), "Unknown")
    )

    print("[segmentation] Segment summary:")
    for tier in ["Bronze", "Silver", "Gold", "Platinum"]:
        seg = customer_metrics[customer_metrics["Tier"] == tier]
        if len(seg):
            print(
                f"  {tier:9s}: {len(seg):4d} customers  |  "
                f"avg revenue ${seg['Total_Revenue'].mean():,.0f}"
            )

    return customer_metrics


# ============================================================================
# ANOMALY DETECTION
# ============================================================================

def ml_anomaly_detection(df: pd.DataFrame, contamination: float = 0.05) -> pd.DataFrame:
    """IsolationForest anomaly detection. Returns the anomalous rows."""
    if not HAS_SKLEARN:
        raise ImportError("scikit-learn is required")

    features = df[["Units_Sold", "Unit_Price", "Total_Sales"]].copy()
    iso = IsolationForest(contamination=contamination, random_state=42)
    labels = iso.fit_predict(features)

    anomalies = df[labels == -1].copy()
    print(
        f"[anomaly] {len(anomalies)} anomalies detected "
        f"({len(anomalies) / len(df) * 100:.1f}% of {len(df)} transactions)"
    )
    return anomalies


# ============================================================================
# EXECUTIVE REPORT
# ============================================================================

def generate_report(df: pd.DataFrame, metrics: dict) -> None:
    """Print an executive summary to stdout."""
    print("\n" + "=" * 60)
    print("AUTODATA ANALYST - EXECUTIVE SUMMARY REPORT")
    print("=" * 60)
    print(f"  Report Date:       {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Analysis Period:   {df['Date'].min()} → {df['Date'].max()}")
    print(f"  Records Analyzed:  {len(df):,}")
    print("-" * 60)
    print(f"  Total Revenue:     ${metrics['total_revenue']:,.2f}")
    print(f"  Avg Transaction:   ${metrics['avg_transaction']:,.2f}")
    print(f"  Total Units Sold:  {metrics['total_units']:,}")
    print(f"  Unique Customers:  {metrics['unique_customers']:,}")

    monthly_sales = df.groupby("Month")["Total_Sales"].sum()
    growth = (
        (monthly_sales.iloc[-1] - monthly_sales.iloc[0]) / monthly_sales.iloc[0]
    ) * 100 if len(monthly_sales) > 1 else 0

    best_month = df.groupby("Month_Name")["Total_Sales"].sum().idxmax()
    best_month_sales = df.groupby("Month_Name")["Total_Sales"].sum().max()
    print(f"\n  Best Month:        {best_month} (${best_month_sales:,.2f})")
    print(f"  Period Growth:     {growth:+.1f}%")
    print("=" * 60)


# ============================================================================
# EXPORT
# ============================================================================

def export_for_powerbi(df: pd.DataFrame, output_path: str = "sales_data_powerbi_ready.csv") -> pd.DataFrame:
    """Write Power BI-optimised CSV. Returns the formatted DataFrame."""
    powerbi_df = df.copy()
    powerbi_df["Date"] = pd.to_datetime(powerbi_df["Date"]).dt.strftime("%Y-%m-%d")
    powerbi_df["Revenue_Category"] = pd.cut(
        powerbi_df["Total_Sales"],
        bins=[0, 1_000, 5_000, 10_000, float("inf")],
        labels=["Low", "Medium", "High", "Premium"],
    )
    powerbi_df = powerbi_df.sort_values("Date")
    powerbi_df.to_csv(output_path, index=False)
    print(f"[export] Saved {len(powerbi_df)} records to '{output_path}'")
    return powerbi_df
