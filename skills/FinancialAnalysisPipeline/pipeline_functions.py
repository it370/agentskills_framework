"""
Financial Analysis Pipeline Functions

These functions are used in the FinancialAnalysisPipeline skill
to perform mathematical computations on financial data.
"""
from typing import Dict, Any, List


def compute_financial_metrics(raw_financial_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute financial metrics from raw sales and expense data.
    
    This function calculates:
    - Total revenue and expenses
    - Gross and net profit
    - Profit margins and ROI
    - Tax liability
    - Deficit status
    
    Args:
        raw_financial_data: Dictionary containing:
            - sales_data: Query result with sales information
            - expense_data: Query result with expense information
            
    Returns:
        Dictionary with computed financial metrics:
        {
            "total_revenue": float,
            "total_expenses": float,
            "gross_profit": float,
            "profit_margin": float,
            "tax_liability": float,
            "tax_rate": float,
            "net_profit": float,
            "is_deficit": bool,
            "roi": float
        }
    
    Example:
        >>> data = {
        ...     "sales_data": {"query_result": [{"total_revenue": 25000}, {"total_revenue": 18000}]},
        ...     "expense_data": {"query_result": [{"total_expense": 15000}, {"total_expense": 5000}]}
        ... }
        >>> metrics = compute_financial_metrics(data)
        >>> metrics["net_profit"]
        17200.0
    """
    # Extract data from query results
    sales = raw_financial_data.get("sales_data", {}).get("query_result", [])
    expenses = raw_financial_data.get("expense_data", {}).get("query_result", [])
    
    # Calculate total revenue from all sales
    total_revenue = sum(item.get("total_revenue", 0) for item in sales)
    
    # Calculate total expenses from all expense categories
    total_expenses = sum(item.get("total_expense", 0) for item in expenses)
    
    # Compute gross profit (before tax)
    gross_profit = total_revenue - total_expenses
    
    # Calculate profit margin as percentage of revenue
    profit_margin = (gross_profit / total_revenue) if total_revenue > 0 else 0
    
    # Tax calculation (20% on positive profit)
    tax_rate = 0.20
    tax_liability = gross_profit * tax_rate if gross_profit > 0 else 0
    
    # Net profit after tax
    net_profit = gross_profit - tax_liability
    
    # Determine deficit status
    is_deficit = total_expenses > total_revenue
    
    # Calculate ROI (return on investment)
    roi = (net_profit / total_expenses * 100) if total_expenses > 0 else 0
    
    return {
        "total_revenue": round(total_revenue, 2),
        "total_expenses": round(total_expenses, 2),
        "gross_profit": round(gross_profit, 2),
        "profit_margin": round(profit_margin, 4),
        "tax_liability": round(tax_liability, 2),
        "tax_rate": tax_rate,
        "net_profit": round(net_profit, 2),
        "is_deficit": is_deficit,
        "roi": round(roi, 2)
    }


def format_financial_report(computed_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format computed metrics into a comprehensive financial report.
    
    This function takes raw computed metrics and structures them into
    a user-friendly report format with categorized sections.
    
    Args:
        computed_metrics: Output from compute_financial_metrics containing:
            - total_revenue, total_expenses, gross_profit, net_profit
            - profit_margin, roi, tax_rate, tax_liability
            - is_deficit
            
    Returns:
        Formatted financial report dictionary with sections:
        - report_type: Report category
        - status: "surplus" or "deficit"
        - summary: Key financial figures
        - metrics: Formatted percentage metrics
        - taxation: Tax-related information
        - health: Business health indicators
    
    Example:
        >>> metrics = {
        ...     "total_revenue": 43000,
        ...     "total_expenses": 23000,
        ...     "gross_profit": 20000,
        ...     "net_profit": 16000,
        ...     "profit_margin": 0.465,
        ...     "roi": 69.57,
        ...     "tax_rate": 0.20,
        ...     "tax_liability": 4000,
        ...     "is_deficit": False
        ... }
        >>> report = format_financial_report(metrics)
        >>> report["status"]
        'surplus'
        >>> report["metrics"]["profit_margin"]
        '46.5%'
    """
    return {
        "report_type": "Financial Analysis",
        "status": "deficit" if computed_metrics["is_deficit"] else "surplus",
        "summary": {
            "total_revenue": computed_metrics["total_revenue"],
            "total_expenses": computed_metrics["total_expenses"],
            "gross_profit": computed_metrics["gross_profit"],
            "net_profit": computed_metrics["net_profit"],
            "is_deficit": computed_metrics["is_deficit"]
        },
        "metrics": {
            "profit_margin": f"{computed_metrics['profit_margin'] * 100:.1f}%",
            "roi": f"{computed_metrics['roi']:.1f}%",
            "tax_rate": f"{computed_metrics['tax_rate'] * 100:.0f}%"
        },
        "taxation": {
            "tax_liability": computed_metrics["tax_liability"],
            "effective_rate": computed_metrics["tax_rate"],
            "description": f"Tax calculated at {computed_metrics['tax_rate'] * 100:.0f}% on gross profit"
        },
        "health": {
            "is_profitable": not computed_metrics["is_deficit"],
            "needs_attention": computed_metrics["profit_margin"] < 0.10,
            "performance": (
                "excellent" if computed_metrics["profit_margin"] > 0.30 else
                "good" if computed_metrics["profit_margin"] > 0.15 else
                "fair" if computed_metrics["profit_margin"] > 0.05 else
                "poor"
            )
        }
    }


def calculate_growth_metrics(
    current_metrics: Dict[str, Any],
    previous_metrics: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate growth metrics by comparing current to previous period.
    
    Optional function for period-over-period analysis.
    
    Args:
        current_metrics: Financial metrics for current period
        previous_metrics: Financial metrics for previous period
        
    Returns:
        Dictionary with growth percentages and trends
    """
    def calculate_growth(current: float, previous: float) -> float:
        if previous == 0:
            return 0 if current == 0 else 100
        return ((current - previous) / previous) * 100
    
    return {
        "revenue_growth": calculate_growth(
            current_metrics["total_revenue"],
            previous_metrics["total_revenue"]
        ),
        "expense_growth": calculate_growth(
            current_metrics["total_expenses"],
            previous_metrics["total_expenses"]
        ),
        "profit_growth": calculate_growth(
            current_metrics["net_profit"],
            previous_metrics["net_profit"]
        ),
        "margin_improvement": (
            current_metrics["profit_margin"] - previous_metrics["profit_margin"]
        ) * 100,
        "trend": (
            "improving" if current_metrics["net_profit"] > previous_metrics["net_profit"]
            else "declining" if current_metrics["net_profit"] < previous_metrics["net_profit"]
            else "stable"
        )
    }
