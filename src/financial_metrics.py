"""
Financial metrics calculation, anomaly detection, and executive summary generator.

Computes financial KPIs (Gross Margin, Net Margin, MoM Growth, Outliers)
and generates professional executive summaries.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from langchain_groq import ChatGroq

logger = logging.getLogger("financial_analyst.metrics")


def identify_financial_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """
    Intelligently identify financial column roles from DataFrame column names.
    
    Returns a dict with mapped column names for:
    revenue, cost, profit, units, date, period, category, product, region
    """
    cols = {c.lower().strip(): c for c in df.columns}
    mapping: Dict[str, Optional[str]] = {
        "revenue": None,
        "cost": None,
        "profit": None,
        "units": None,
        "date": None,
        "period": None,
        "category": None,
        "product": None,
        "region": None,
    }

    for col_lower, orig_col in cols.items():
        if not mapping["revenue"] and any(k in col_lower for k in ["revenue", "sales", "turnover", "total_amount", "gross_sales"]):
            mapping["revenue"] = orig_col
        elif not mapping["cost"] and any(k in col_lower for k in ["cost", "expense", "cogs", "expenditure"]):
            mapping["cost"] = orig_col
        elif not mapping["profit"] and any(k in col_lower for k in ["profit", "net_income", "earnings", "margin_amount"]):
            mapping["profit"] = orig_col
        elif not mapping["units"] and any(k in col_lower for k in ["units", "qty", "quantity", "volume", "sold"]):
            mapping["units"] = orig_col
        elif not mapping["date"] and any(k in col_lower for k in ["date", "timestamp", "time"]):
            mapping["date"] = orig_col
        elif not mapping["period"] and any(k in col_lower for k in ["month", "quarter", "year", "period", "week"]):
            mapping["period"] = orig_col
        elif not mapping["category"] and any(k in col_lower for k in ["category", "segment", "department", "type"]):
            mapping["category"] = orig_col
        elif not mapping["product"] and any(k in col_lower for k in ["product", "item", "sku", "service"]):
            mapping["product"] = orig_col
        elif not mapping["region"] and any(k in col_lower for k in ["region", "territory", "country", "zone", "location"]):
            mapping["region"] = orig_col

    # Fallback for revenue/profit if still none found: look at numeric columns
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if not mapping["revenue"] and numeric_cols:
        mapping["revenue"] = numeric_cols[0]
    if not mapping["profit"] and len(numeric_cols) > 1:
        # Check if second numeric might be profit or cost
        mapping["profit"] = numeric_cols[-1]

    return mapping


def calculate_kpis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate financial KPIs, growth rates, segment contributions, and anomalies.
    
    Returns a comprehensive dictionary of financial indicators.
    """
    col_map = identify_financial_columns(df)
    rev_col = col_map["revenue"]
    cost_col = col_map["cost"]
    profit_col = col_map["profit"]
    units_col = col_map["units"]
    period_col = col_map["period"] or col_map["date"]
    cat_col = col_map["category"] or col_map["product"] or col_map["region"]

    metrics: Dict[str, Any] = {
        "col_map": col_map,
        "row_count": len(df),
        "total_revenue": 0.0,
        "total_cost": 0.0,
        "total_profit": 0.0,
        "gross_margin_pct": 0.0,
        "net_margin_pct": 0.0,
        "avg_transaction_val": 0.0,
        "total_units": 0,
        "growth": {},
        "top_performers": {},
        "anomalies": [],
        "has_financial_data": rev_col is not None,
    }

    if not rev_col or rev_col not in df.columns:
        return metrics

    # Calculate Core Totals
    try:
        metrics["total_revenue"] = float(df[rev_col].sum())
        metrics["avg_transaction_val"] = float(df[rev_col].mean())
    except Exception as e:
        logger.warning("Error calculating revenue totals: %s", e)

    if cost_col and cost_col in df.columns:
        try:
            metrics["total_cost"] = float(df[cost_col].sum())
            if metrics["total_revenue"] > 0:
                metrics["gross_margin_pct"] = (
                    (metrics["total_revenue"] - metrics["total_cost"]) / metrics["total_revenue"]
                ) * 100
        except Exception as e:
            logger.warning("Error calculating cost totals: %s", e)

    if profit_col and profit_col in df.columns:
        try:
            metrics["total_profit"] = float(df[profit_col].sum())
            if metrics["total_revenue"] > 0:
                metrics["net_margin_pct"] = (
                    metrics["total_profit"] / metrics["total_revenue"]
                ) * 100
        except Exception as e:
            logger.warning("Error calculating profit totals: %s", e)
    elif cost_col and cost_col in df.columns:
        # If profit col missing but cost col exists, profit = revenue - cost
        metrics["total_profit"] = metrics["total_revenue"] - metrics["total_cost"]
        if metrics["total_revenue"] > 0:
            metrics["net_margin_pct"] = (
                metrics["total_profit"] / metrics["total_revenue"]
            ) * 100

    if units_col and units_col in df.columns:
        try:
            metrics["total_units"] = int(df[units_col].sum())
        except Exception:
            pass

    # Period-over-Period / MoM Growth
    if period_col and period_col in df.columns:
        try:
            if col_map["date"] and col_map["date"] in df.columns:
                # Sort chronologically by date first, then group by period keeping order
                sorted_df = df.copy()
                try:
                    sorted_df["_parsed_date"] = pd.to_datetime(sorted_df[col_map["date"]])
                    sorted_df = sorted_df.sort_values("_parsed_date")
                except Exception:
                    sorted_df = sorted_df.sort_values(col_map["date"])
                period_grp = sorted_df.groupby(period_col, sort=False)[rev_col].sum()
            else:
                period_grp = df.groupby(period_col)[rev_col].sum()

            pct_change = period_grp.pct_change() * 100
            metrics["growth"] = {
                "periods": [str(p) for p in period_grp.index],
                "values": [float(v) for v in period_grp.values],
                "pct_changes": [None if np.isnan(c) else round(float(c), 2) for c in pct_change.values],
                "avg_growth_pct": round(float(pct_change.dropna().mean()), 2) if not pct_change.dropna().empty else 0.0,
                "latest_growth_pct": round(float(pct_change.dropna().iloc[-1]), 2) if not pct_change.dropna().empty else 0.0,
            }
        except Exception as e:
            logger.warning("Could not compute period growth: %s", e)

    # Top & Bottom Performers Breakdown
    for dim_name in ["category", "product", "region"]:
        col = col_map.get(dim_name)
        if col and col in df.columns:
            try:
                grouped = df.groupby(col)[rev_col].sum().sort_values(ascending=False)
                top_name = str(grouped.index[0])
                top_val = float(grouped.iloc[0])
                top_share = (top_val / metrics["total_revenue"] * 100) if metrics["total_revenue"] > 0 else 0
                metrics["top_performers"][col] = {
                    "top_name": top_name,
                    "top_val": top_val,
                    "top_share_pct": round(top_share, 1),
                    "items_count": len(grouped),
                }
            except Exception as e:
                logger.warning("Could not compute top performer for %s: %s", col, e)

    # Outlier & Anomaly Detection
    try:
        # Check for negative profit or negative margin
        if profit_col and profit_col in df.columns:
            neg_profit = df[df[profit_col] < 0]
            if not neg_profit.empty:
                metrics["anomalies"].append({
                    "type": "negative_profit",
                    "count": len(neg_profit),
                    "description": f"Found {len(neg_profit)} transaction(s) with negative profit (losses).",
                })

        # Check for statistical revenue outliers via IQR
        rev_series = df[rev_col].dropna()
        q1 = rev_series.quantile(0.25)
        q3 = rev_series.quantile(0.75)
        iqr = q3 - q1
        outliers = df[(df[rev_col] > q3 + 2.5 * iqr) | (df[rev_col] < q1 - 2.5 * iqr)]
        if not outliers.empty:
            metrics["anomalies"].append({
                "type": "revenue_spike",
                "count": len(outliers),
                "description": f"Detected {len(outliers)} statistical outlier(s) with anomalous transaction values.",
            })
    except Exception as e:
        logger.warning("Anomaly detection error: %s", e)

    return metrics


def generate_executive_summary(df: pd.DataFrame, llm: ChatGroq, file_name: str = "Dataset") -> str:
    """
    Generate an authoritative Executive Financial Summary using LLM
    anchored on computed statistical metrics.
    """
    kpis = calculate_kpis(df)
    col_map = kpis["col_map"]

    rev_str = f"${kpis['total_revenue']:,.2f}" if kpis["total_revenue"] else "N/A"
    profit_str = f"${kpis['total_profit']:,.2f}" if kpis["total_profit"] else "N/A"
    net_margin_str = f"{kpis['net_margin_pct']:.2f}%" if kpis["net_margin_pct"] else "N/A"
    cost_str = f"${kpis['total_cost']:,.2f}" if kpis["total_cost"] else "N/A"
    units_str = f"{kpis['total_units']:,}" if kpis["total_units"] else "N/A"
    avg_tx_str = f"${kpis['avg_transaction_val']:,.2f}" if kpis["avg_transaction_val"] else "N/A"

    performers_text = []
    for dim, info in kpis["top_performers"].items():
        performers_text.append(f"- **{dim}**: Top driver is `{info['top_name']}` generating ${info['top_val']:,.2f} ({info['top_share_pct']}% of revenue)")
    performers_summary = "\n".join(performers_text) if performers_text else "None identified"

    growth_summary = "Not available"
    if kpis["growth"]:
        growth_summary = (
            f"Average Period Growth: {kpis['growth']['avg_growth_pct']:+.2f}%, "
            f"Latest Period Growth: {kpis['growth']['latest_growth_pct']:+.2f}% "
            f"across {len(kpis['growth']['periods'])} periods."
        )

    anomalies_text = []
    for a in kpis["anomalies"]:
        anomalies_text.append(f"- {a['description']}")
    anomalies_summary = "\n".join(anomalies_text) if anomalies_text else "No significant anomalies or loss-making transactions detected."

    prompt = f"""You are a Senior Financial Analyst and Data Strategist.
Review the following verified statistical data from financial dataset '{file_name}' ({kpis['row_count']:,} total records) and provide an insightful, polished Executive Financial Summary.

=== VERIFIED METRICS ===
- Total Revenue: {rev_str}
- Total Operating Cost: {cost_str}
- Net Profit: {profit_str}
- Net Margin: {net_margin_str}
- Total Units / Volume: {units_str}
- Average Transaction Value: {avg_tx_str}
- Growth Trajectory: {growth_summary}

=== SEGMENT DRIVERS ===
{performers_summary}

=== ANOMALIES & RISK FLAGS ===
{anomalies_summary}

=== INSTRUCTIONS ===
Write an executive summary formatted with standard Markdown using these exact 5 sections:
1. 🏛️ **Executive Verdict & Financial Health**: A 2-sentence bottom-line assessment of overall commercial viability and profitability.
2. 📊 **Key Financial Highlights**: Bulleted review of revenue, net margins, and operating efficiency.
3. 🚀 **Growth & Segment Drivers**: Analysis of primary contributors and growth velocity.
4. ⚠️ **Risk Factors & Margin Watch**: Highlight anomalies, cost pressures, or dependencies.
5. 🎯 **Strategic Recommendations**: 3 concrete, high-impact tactical actions to optimize profit and expansion.

Be direct, insightful, and use the exact calculated figures. Do not make up outside numbers.
"""

    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        import re
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        return content
    except Exception as e:
        logger.error("Failed to generate executive summary: %s", e)
        # Deterministic fallback summary if LLM call fails
        return f"""### 🏛️ Executive Financial Summary ({file_name})

**Financial Health Overview:**
The dataset spans **{kpis['row_count']:,}** records with a total recorded revenue of **{rev_str}** and net profit of **{profit_str}**, representing an overall net margin of **{net_margin_str}**.

**Key Metrics:**
- **Total Revenue:** {rev_str}
- **Total Cost:** {cost_str}
- **Net Profit:** {profit_str} ({net_margin_str} Margin)
- **Average Transaction:** {avg_tx_str}
- **Growth Velocity:** {growth_summary}

**Primary Drivers:**
{performers_summary}

**Risks & Anomalies:**
{anomalies_summary}
"""
