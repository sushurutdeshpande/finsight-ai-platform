"""Unit tests for financial metrics calculation and KPI detection."""

import pandas as pd
import pytest
from src.financial_metrics import identify_financial_columns, calculate_kpis


@pytest.fixture
def sample_sales_df():
    return pd.DataFrame({
        "Date": ["2024-01-05", "2024-01-12", "2024-02-03", "2024-02-09"],
        "Month": ["January", "January", "February", "February"],
        "Product": ["Product A", "Product B", "Product A", "Product B"],
        "Category": ["Electronics", "Clothing", "Electronics", "Clothing"],
        "Region": ["North", "South", "South", "North"],
        "Units_Sold": [10, 20, 15, 25],
        "Revenue": [1000.0, 2000.0, 1500.0, 2500.0],
        "Cost": [600.0, 1200.0, 900.0, 1500.0],
        "Profit": [400.0, 800.0, 600.0, 1000.0],
    })


def test_identify_columns(sample_sales_df):
    mapping = identify_financial_columns(sample_sales_df)
    assert mapping["revenue"] == "Revenue"
    assert mapping["cost"] == "Cost"
    assert mapping["profit"] == "Profit"
    assert mapping["units"] == "Units_Sold"
    assert mapping["category"] == "Category"
    assert mapping["product"] == "Product"
    assert mapping["region"] == "Region"


def test_calculate_kpis(sample_sales_df):
    kpis = calculate_kpis(sample_sales_df)
    assert kpis["has_financial_data"] is True
    assert kpis["total_revenue"] == 7000.0
    assert kpis["total_cost"] == 4200.0
    assert kpis["total_profit"] == 2800.0
    assert kpis["net_margin_pct"] == pytest.approx(40.0)
    assert kpis["gross_margin_pct"] == pytest.approx(40.0)
    assert kpis["total_units"] == 70
    assert kpis["avg_transaction_val"] == 1750.0
    assert "Category" in kpis["top_performers"]
    assert kpis["top_performers"]["Category"]["top_name"] == "Clothing"
