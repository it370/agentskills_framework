---
name: FinancialAnalysisPipeline
description: |
  Comprehensive financial analysis pipeline that:
  1. Fetches sales data from database
  2. Fetches expenses data from database
  3. Uses FinancialAnalyzer skill (LLM) for logical reasoning
  4. Performs tax and profit calculations via Python function
  5. Outputs comprehensive financial report

requires:
  - company_id
  - analysis_period

produces:
  - financial_report

executor: action

action:
  type: data_pipeline
  steps:
    # Step 1: Fetch sales data from postgres
    - type: query
      name: fetch_sales
      source: postgres
      credential_ref: postgres_aiven_cloud_db
      query: |
        SELECT 
          product_id,
          product_name,
          SUM(quantity) as units_sold,
          SUM(quantity * unit_price) as total_revenue
        FROM sales
        WHERE company_id = '{company_id}'
          AND sale_date >= '{analysis_period}'
        GROUP BY product_id, product_name
        ORDER BY total_revenue DESC
      output: sales_data
    
    # Step 2: Fetch expenses data from postgres
    - type: query
      name: fetch_expenses
      source: postgres
      credential_ref: postgres_aiven_cloud_db
      query: |
        SELECT 
          expense_category,
          SUM(amount) as total_expense,
          COUNT(*) as transaction_count
        FROM expenses
        WHERE company_id = '{company_id}'
          AND expense_date >= '{analysis_period}'
        GROUP BY expense_category
        ORDER BY total_expense DESC
      output: expense_data
    
    # Step 3: Prepare data for LLM analysis
    # Merge sales and expenses into analysis context
    - type: merge
      name: combine_financial_data
      inputs:
        - sales_data
        - expense_data
      output: raw_financial_data
    
    # Step 4: AI-Powered Financial Analysis (LLM Skill Invocation)
    # This invokes the FinancialAnalyzer skill for logical reasoning
    - type: skill
      name: llm_analysis
      skill: FinancialAnalyzer
      inputs:
        - raw_financial_data
      # FinancialAnalyzer produces: is_deficit, total_amount, total_profit, 
      #   gross_income, business_health_score, recommendations
      # These are automatically added to the pipeline context
    
    # Step 5: Mathematical computations (Python function)
    - type: transform
      name: calculate_financial_metrics
      function: compute_financial_metrics
      inputs:
        - raw_financial_data
      output: computed_metrics
    
    # Step 6: Format final output
    - type: transform
      name: format_report
      function: format_financial_report
      inputs:
        - computed_metrics
      output: financial_report

---

# Financial Analysis Pipeline

This skill demonstrates a complete data pipeline that orchestrates multiple data sources, reasoning, and computations.

## Pipeline Flow

```
1. Query Sales DB → sales_data
2. Query Expenses DB → expense_data
3. Merge Data → raw_financial_data
4. **Invoke FinancialAnalyzer Skill (LLM)** → AI reasoning outputs
5. Compute Metrics (Python) → computed_metrics
6. Format Report → financial_report
```

## Data Flow Example

### Step 1 Output (sales_data)
```json
{
  "query_result": [
    {"product_id": 1, "product_name": "Widget A", "units_sold": 500, "total_revenue": 25000},
    {"product_id": 2, "product_name": "Widget B", "units_sold": 300, "total_revenue": 18000}
  ],
  "row_count": 2
}
```

### Step 2 Output (expense_data)
```json
{
  "query_result": [
    {"expense_category": "Salary", "total_expense": 15000, "transaction_count": 10},
    {"expense_category": "Rent", "total_expense": 5000, "transaction_count": 1},
    {"expense_category": "Marketing", "total_expense": 3000, "transaction_count": 5}
  ],
  "row_count": 3
}
```

### Step 3 Output (raw_financial_data)
```json
{
  "sales_data": {...},
  "expense_data": {...}
}
```

### Step 4 Output (LLM Analysis)
The FinancialAnalyzer skill produces:
```json
{
  "is_deficit": false,
  "total_amount": 43000,
  "total_profit": 20000,
  "gross_income": 43000,
  "business_health_score": 78,
  "recommendations": [
    "Increase marketing spend for Widget A (highest revenue generator)",
    "Review salary expenses - represents 65% of total costs",
    "Consider diversifying product line to reduce revenue concentration risk"
  ]
}
```

### Step 5 Output (computed_metrics)
```json
{
  "total_revenue": 43000,
  "total_expenses": 23000,
  "gross_profit": 20000,
  "profit_margin": 0.465,
  "tax_liability": 4000,
  "net_profit": 16000,
  "is_deficit": false
}
```

### Step 6: Final Output (financial_report)
```json
{
  "period": "2024-Q1",
  "company_id": "COMP-123",
  "summary": {
    "total_revenue": 43000,
    "total_expenses": 23000,
    "gross_profit": 20000,
    "net_profit": 16000,
    "is_deficit": false
  },
  "metrics": {
    "profit_margin": "46.5%",
    "roi": "87.0%",
    "tax_rate": "20.0%"
  },
  "ai_insights": {
    "health_score": 78,
    "recommendations": [...]
  },
  "top_products": [...],
  "expense_breakdown": {...}
}
```

## Usage

### Prerequisites
1. Create the required Python functions (see below)
2. Ensure database credentials are configured
3. Database tables must exist: `sales`, `expenses`

### Invoke the Skill
```python
result = await workflow.run({
    "company_id": "COMP-123",
    "analysis_period": "2024-01-01"
})

report = result["financial_report"]
print(f"Net Profit: ${report['summary']['net_profit']}")
print(f"Status: {'Surplus' if not report['summary']['is_deficit'] else 'Deficit'}")
```

## Related Skills

This pipeline should be used with the **FinancialAnalyzer** LLM skill for logical reasoning:

### FinancialAnalyzer Skill (Separate LLM Skill)
```yaml
name: FinancialAnalyzer
description: Analyzes financial data and provides business insights
requires:
  - raw_financial_data
produces:
  - is_deficit
  - total_amount
  - total_profit
  - gross_income
  - business_health_score
  - recommendations
executor: llm
prompt: |
  Analyze the following financial data and provide comprehensive business insights.
  
  Sales Data:
  {raw_financial_data.sales_data.query_result}
  
  Expense Data:
  {raw_financial_data.expense_data.query_result}
  
  Calculate and provide:
  1. is_deficit: boolean - whether expenses exceed revenue
  2. total_amount: total revenue generated
  3. total_profit: revenue minus expenses
  4. gross_income: revenue before any deductions
  5. business_health_score: 0-100 score based on financial health
  6. recommendations: array of actionable business recommendations
  
  Return your analysis in JSON format with these exact keys.
```

## Required Python Functions

Create these in `skills/FinancialAnalysisPipeline/pipeline_functions.py`:

```python
"""
Financial Analysis Pipeline Functions
"""
from typing import Dict, Any, List


def compute_financial_metrics(raw_financial_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute financial metrics from raw data.
    
    Args:
        raw_financial_data: Merged sales and expense data
        
    Returns:
        Dictionary with computed financial metrics
    """
    # Extract data
    sales = raw_financial_data.get("sales_data", {}).get("query_result", [])
    expenses = raw_financial_data.get("expense_data", {}).get("query_result", [])
    
    # Calculate totals
    total_revenue = sum(item.get("total_revenue", 0) for item in sales)
    total_expenses = sum(item.get("total_expense", 0) for item in expenses)
    
    # Compute metrics
    gross_profit = total_revenue - total_expenses
    profit_margin = (gross_profit / total_revenue) if total_revenue > 0 else 0
    
    # Tax calculation (20% on profit)
    tax_rate = 0.20
    tax_liability = gross_profit * tax_rate if gross_profit > 0 else 0
    net_profit = gross_profit - tax_liability
    
    # Determine deficit status
    is_deficit = total_expenses > total_revenue
    
    return {
        "total_revenue": round(total_revenue, 2),
        "total_expenses": round(total_expenses, 2),
        "gross_profit": round(gross_profit, 2),
        "profit_margin": round(profit_margin, 4),
        "tax_liability": round(tax_liability, 2),
        "tax_rate": tax_rate,
        "net_profit": round(net_profit, 2),
        "is_deficit": is_deficit,
        "roi": round((net_profit / total_expenses * 100) if total_expenses > 0 else 0, 2)
    }


def format_financial_report(computed_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format computed metrics into a comprehensive financial report.
    
    Args:
        computed_metrics: Output from compute_financial_metrics
        
    Returns:
        Formatted financial report
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
            "effective_rate": computed_metrics["tax_rate"]
        },
        "health": {
            "is_profitable": not computed_metrics["is_deficit"],
            "needs_attention": computed_metrics["profit_margin"] < 0.10
        }
    }
```

## Register Functions

Add to `actions/__init__.py`:
```python
from skills.FinancialAnalysisPipeline.pipeline_functions import (
    compute_financial_metrics,
    format_financial_report
)

# These will be auto-registered in the action function registry
```

## Database Setup

```sql
-- Sales table
CREATE TABLE sales (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(50),
    product_id INT,
    product_name VARCHAR(255),
    quantity INT,
    unit_price DECIMAL(10, 2),
    sale_date DATE
);

-- Expenses table
CREATE TABLE expenses (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(50),
    expense_category VARCHAR(100),
    amount DECIMAL(10, 2),
    expense_date DATE,
    description TEXT
);

-- Sample data
INSERT INTO sales (company_id, product_id, product_name, quantity, unit_price, sale_date) VALUES
('COMP-123', 1, 'Widget A', 500, 50.00, '2024-01-15'),
('COMP-123', 2, 'Widget B', 300, 60.00, '2024-02-10');

INSERT INTO expenses (company_id, expense_category, amount, expense_date) VALUES
('COMP-123', 'Salary', 15000, '2024-01-31'),
('COMP-123', 'Rent', 5000, '2024-02-01'),
('COMP-123', 'Marketing', 3000, '2024-02-15');
```

## Testing

```bash
# Test via UI
curl -X POST http://localhost:8000/admin/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Analyze financial performance for Q1",
    "company_id": "COMP-123",
    "analysis_period": "2024-01-01"
  }'
```

## Workflow Orchestration

To use with the LLM reasoning skill, create a workflow:

```yaml
# Option 1: Sequential Skills
1. Run FinancialAnalysisPipeline (steps 1,2,4,5)
2. Run FinancialAnalyzer (LLM reasoning on results)
3. Merge outputs

# Option 2: Embedded in Pipeline (recommended)
Modify the pipeline to include a "skill" step that invokes FinancialAnalyzer
between step 3 and 4.
```

## Key Features Demonstrated

✅ **Multiple Data Queries**: Two separate postgres queries  
✅ **Data Merging**: Combining results from multiple sources  
✅ **Python Functions**: Custom business logic in pipeline  
✅ **Result Mapping**: Single `produces` key gets entire pipeline output  
✅ **Credential Management**: Secure database access  
✅ **Complex Computations**: Tax, profit, margins, ROI  
✅ **Type Safety**: Structured outputs with validation  

## Next Steps

1. **Add LLM Step**: Insert FinancialAnalyzer skill between merge and compute
2. **Add Caching**: Cache database results for repeated analyses
3. **Add Visualization**: Generate charts from report data
4. **Add Alerts**: Trigger notifications on deficit or low margins
