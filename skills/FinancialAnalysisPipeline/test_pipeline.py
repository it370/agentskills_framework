"""
Test script for FinancialAnalysisPipeline

This script tests the pipeline functions independently before running the full skill.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from skills.FinancialAnalysisPipeline.pipeline_functions import (
    compute_financial_metrics,
    format_financial_report,
    calculate_growth_metrics
)


def test_compute_metrics():
    """Test the compute_financial_metrics function"""
    print("\n=== Testing compute_financial_metrics ===")
    
    # Mock data that simulates database query results
    test_data = {
        "sales_data": {
            "query_result": [
                {
                    "product_id": 1,
                    "product_name": "Widget A",
                    "units_sold": 500,
                    "total_revenue": 25000
                },
                {
                    "product_id": 2,
                    "product_name": "Widget B",
                    "units_sold": 300,
                    "total_revenue": 18000
                }
            ],
            "row_count": 2
        },
        "expense_data": {
            "query_result": [
                {
                    "expense_category": "Salary",
                    "total_expense": 15000,
                    "transaction_count": 10
                },
                {
                    "expense_category": "Rent",
                    "total_expense": 5000,
                    "transaction_count": 1
                },
                {
                    "expense_category": "Marketing",
                    "total_expense": 3000,
                    "transaction_count": 5
                }
            ],
            "row_count": 3
        }
    }
    
    # Compute metrics
    metrics = compute_financial_metrics(test_data)
    
    # Assertions
    assert metrics["total_revenue"] == 43000.00, f"Expected 43000, got {metrics['total_revenue']}"
    assert metrics["total_expenses"] == 23000.00, f"Expected 23000, got {metrics['total_expenses']}"
    assert metrics["gross_profit"] == 20000.00, f"Expected 20000, got {metrics['gross_profit']}"
    assert metrics["net_profit"] == 16000.00, f"Expected 16000, got {metrics['net_profit']}"
    assert metrics["tax_liability"] == 4000.00, f"Expected 4000, got {metrics['tax_liability']}"
    assert metrics["is_deficit"] == False, f"Expected False, got {metrics['is_deficit']}"
    assert 0.46 < metrics["profit_margin"] < 0.47, f"Margin should be ~0.465, got {metrics['profit_margin']}"
    
    print("✓ All assertions passed")
    print(f"  Total Revenue: ${metrics['total_revenue']:,.2f}")
    print(f"  Total Expenses: ${metrics['total_expenses']:,.2f}")
    print(f"  Gross Profit: ${metrics['gross_profit']:,.2f}")
    print(f"  Tax Liability (20%): ${metrics['tax_liability']:,.2f}")
    print(f"  Net Profit: ${metrics['net_profit']:,.2f}")
    print(f"  Profit Margin: {metrics['profit_margin']*100:.1f}%")
    print(f"  ROI: {metrics['roi']:.1f}%")
    print(f"  Status: {'Deficit' if metrics['is_deficit'] else 'Surplus'}")
    
    return metrics


def test_format_report(metrics):
    """Test the format_financial_report function"""
    print("\n=== Testing format_financial_report ===")
    
    report = format_financial_report(metrics)
    
    # Assertions
    assert report["status"] == "surplus", f"Expected surplus, got {report['status']}"
    assert report["report_type"] == "Financial Analysis"
    assert report["summary"]["is_deficit"] == False
    assert report["health"]["is_profitable"] == True
    assert report["metrics"]["profit_margin"] == "46.5%"
    
    print("✓ All assertions passed")
    print(f"  Report Type: {report['report_type']}")
    print(f"  Status: {report['status']}")
    print(f"  Profit Margin: {report['metrics']['profit_margin']}")
    print(f"  ROI: {report['metrics']['roi']}")
    print(f"  Tax Rate: {report['metrics']['tax_rate']}")
    print(f"  Performance: {report['health']['performance']}")
    
    return report


def test_deficit_scenario():
    """Test with deficit scenario (expenses > revenue)"""
    print("\n=== Testing Deficit Scenario ===")
    
    deficit_data = {
        "sales_data": {
            "query_result": [
                {"total_revenue": 10000}
            ]
        },
        "expense_data": {
            "query_result": [
                {"total_expense": 15000}
            ]
        }
    }
    
    metrics = compute_financial_metrics(deficit_data)
    report = format_financial_report(metrics)
    
    assert metrics["is_deficit"] == True, "Should be in deficit"
    assert metrics["gross_profit"] < 0, "Profit should be negative"
    assert report["status"] == "deficit", "Report should show deficit status"
    
    print("✓ Deficit scenario handled correctly")
    print(f"  Revenue: ${metrics['total_revenue']:,.2f}")
    print(f"  Expenses: ${metrics['total_expenses']:,.2f}")
    print(f"  Loss: ${metrics['gross_profit']:,.2f}")
    print(f"  Status: {report['status']}")


def test_growth_metrics():
    """Test the growth metrics calculation"""
    print("\n=== Testing calculate_growth_metrics ===")
    
    current = {
        "total_revenue": 50000,
        "total_expenses": 25000,
        "net_profit": 20000,
        "profit_margin": 0.40
    }
    
    previous = {
        "total_revenue": 40000,
        "total_expenses": 24000,
        "net_profit": 12800,
        "profit_margin": 0.32
    }
    
    growth = calculate_growth_metrics(current, previous)
    
    assert growth["revenue_growth"] == 25.0, f"Expected 25% growth, got {growth['revenue_growth']}"
    assert growth["trend"] == "improving", "Trend should be improving"
    
    print("✓ Growth metrics calculated correctly")
    print(f"  Revenue Growth: {growth['revenue_growth']:.1f}%")
    print(f"  Expense Growth: {growth['expense_growth']:.1f}%")
    print(f"  Profit Growth: {growth['profit_growth']:.1f}%")
    print(f"  Margin Improvement: {growth['margin_improvement']:.1f}%")
    print(f"  Trend: {growth['trend']}")


def main():
    """Run all tests"""
    print("=" * 60)
    print("  FinancialAnalysisPipeline Function Tests")
    print("=" * 60)
    
    try:
        # Test 1: Compute metrics with surplus
        metrics = test_compute_metrics()
        
        # Test 2: Format report
        report = test_format_report(metrics)
        
        # Test 3: Deficit scenario
        test_deficit_scenario()
        
        # Test 4: Growth metrics
        test_growth_metrics()
        
        print("\n" + "=" * 60)
        print("  ✓ ALL TESTS PASSED")
        print("=" * 60)
        print("\nThe pipeline functions are working correctly!")
        print("You can now run the full skill via the workflow.")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
