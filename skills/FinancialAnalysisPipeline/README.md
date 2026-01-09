# Financial Analysis Pipeline - Complete Example

This directory contains a comprehensive example demonstrating a data pipeline skill that:

1. ✅ Fetches sales data from PostgreSQL
2. ✅ Fetches expense data from PostgreSQL (separate query)
3. ✅ Merges both datasets
4. ✅ Performs mathematical computations via Python functions
5. ✅ Formats final output

## Files

- **`skill.md`**: Main skill definition with data pipeline configuration
- **`pipeline_functions.py`**: Python functions for computations and formatting
- **`README.md`**: This file

## Architecture

### Pipeline Flow

```
┌─────────────────────────────────────────────────────────────┐
│                 FinancialAnalysisPipeline                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Step 1: Query Sales                                        │
│  ┌────────────────────────────────────────┐                │
│  │ SELECT * FROM sales                    │                │
│  │ WHERE company_id = '{company_id}'      │                │
│  └────────────────┬───────────────────────┘                │
│                   ↓                                          │
│            sales_data = {                                    │
│              query_result: [...],                           │
│              row_count: N                                    │
│            }                                                 │
│                                                              │
│  Step 2: Query Expenses                                     │
│  ┌────────────────────────────────────────┐                │
│  │ SELECT * FROM expenses                 │                │
│  │ WHERE company_id = '{company_id}'      │                │
│  └────────────────┬───────────────────────┘                │
│                   ↓                                          │
│            expense_data = {                                  │
│              query_result: [...],                           │
│              row_count: N                                    │
│            }                                                 │
│                                                              │
│  Step 3: Merge Data                                         │
│  ┌────────────────────────────────────────┐                │
│  │ Combine sales_data + expense_data      │                │
│  └────────────────┬───────────────────────┘                │
│                   ↓                                          │
│            raw_financial_data = {                           │
│              sales_data: {...},                             │
│              expense_data: {...}                            │
│            }                                                 │
│                                                              │
│  Step 4: Invoke FinancialAnalyzer (LLM Skill)              │
│  ┌────────────────────────────────────────┐                │
│  │ AI-Powered Financial Analysis          │                │
│  │ • Logical reasoning on data            │                │
│  │ • Business health scoring (0-100)      │                │
│  │ • Strategic recommendations            │                │
│  │ • Pattern recognition                  │                │
│  └────────────────┬───────────────────────┘                │
│                   ↓                                          │
│            LLM outputs = {                                  │
│              is_deficit: false,                             │
│              total_amount: 43000,                           │
│              total_profit: 20000,                           │
│              business_health_score: 78,                     │
│              recommendations: [...]                         │
│            }                                                 │
│                                                              │
│  Step 5: Compute Metrics (Python Function)                 │
│  ┌────────────────────────────────────────┐                │
│  │ compute_financial_metrics()            │                │
│  │ • Calculate totals                     │                │
│  │ • Compute profit/margins               │                │
│  │ • Calculate tax (20% on profit)        │                │
│  │ • Determine deficit status             │                │
│  └────────────────┬───────────────────────┘                │
│                   ↓                                          │
│            computed_metrics = {                             │
│              total_revenue: 43000,                          │
│              total_expenses: 23000,                         │
│              gross_profit: 20000,                           │
│              net_profit: 16000,                             │
│              tax_liability: 4000,                           │
│              profit_margin: 0.465,                          │
│              roi: 69.57,                                     │
│              is_deficit: false                              │
│            }                                                 │
│                                                              │
│  Step 5: Format Report (Python Function)                   │
│  ┌────────────────────────────────────────┐                │
│  │ format_financial_report()              │                │
│  │ • Structure into sections              │                │
│  │ • Format percentages                   │                │
│  │ • Add health indicators                │                │
│  │ • Incorporate AI insights              │                │
│  └────────────────┬───────────────────────┘                │
│                   ↓                                          │
│            financial_report = {                             │
│              status: "surplus",                             │
│              summary: {...},                                │
│              metrics: {...},                                │
│              taxation: {...},                               │
│              health: {...},                                  │
│              ai_insights: {                                  │
│                health_score: 78,                            │
│                recommendations: [...]                       │
│              }                                               │
│            }                                                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Key Concepts Demonstrated

### 1. Single `produces` Key

The skill defines only one output:

```yaml
produces:
  - financial_report
```

**Result**: The entire pipeline output (a complex nested object) is stored under this single key in `data_store`.

```python
data_store["financial_report"] = {
    # Entire formatted report object
    "status": "surplus",
    "summary": {...},
    "metrics": {...}
}
```

### 2. Multiple Data Queries

Two separate PostgreSQL queries in the same pipeline:
- `fetch_sales`: Retrieves sales data
- `fetch_expenses`: Retrieves expense data

Each query result includes `query_result` and `row_count`.

### 3. Data Merging

The `merge` step combines multiple inputs:

```yaml
- type: merge
  name: combine_financial_data
  inputs:
    - sales_data
    - expense_data
  output: raw_financial_data
```

Result:
```json
{
  "sales_data": {...},
  "expense_data": {...}
}
```

### 4. Python Functions in Pipeline

Functions are called by name from the action registry:

```yaml
- type: function
  name: calculate_financial_metrics
  function: compute_financial_metrics  # ← Registered function name
  inputs:
    - raw_financial_data
  output: computed_metrics
```

The framework:
1. Looks up `compute_financial_metrics` in `_ACTION_FUNCTION_REGISTRY`
2. Calls it with the specified inputs
3. Stores the result under `computed_metrics`

### 5. LLM Skill Invocation in Pipeline

**NEW**: Pipelines can now invoke other skills (like LLM skills) for reasoning:

```yaml
- type: skill
  name: llm_analysis
  skill: FinancialAnalyzer  # ← Skill name from registry
  inputs:
    - raw_financial_data
```

The framework:
1. Looks up `FinancialAnalyzer` in `SKILL_REGISTRY`
2. Executes it with the specified inputs
3. **All outputs from the skill are added to pipeline context**

In our example, `FinancialAnalyzer` produces 6 keys:
- `is_deficit`
- `total_amount`
- `total_profit`  
- `gross_income`
- `business_health_score`
- `recommendations`

All of these become available for use in subsequent pipeline steps!

### 6. Result Mapping

Since `produces` has only **1 key** (`financial_report`), the entire final pipeline output is stored under that key.

If `produces` had multiple keys like:
```yaml
produces:
  - summary
  - metrics
  - health
```

Then the framework would map by position:
- First output → `summary`
- Second output → `metrics`
- Third output → `health`

## Database Setup

```sql
-- Create tables
CREATE TABLE sales (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(50),
    product_id INT,
    product_name VARCHAR(255),
    quantity INT,
    unit_price DECIMAL(10, 2),
    sale_date DATE
);

CREATE TABLE expenses (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(50),
    expense_category VARCHAR(100),
    amount DECIMAL(10, 2),
    expense_date DATE,
    description TEXT
);

-- Insert sample data
INSERT INTO sales (company_id, product_id, product_name, quantity, unit_price, sale_date) VALUES
('COMP-123', 1, 'Widget A', 500, 50.00, '2024-01-15'),
('COMP-123', 2, 'Widget B', 300, 60.00, '2024-02-10');

INSERT INTO expenses (company_id, expense_category, amount, expense_date) VALUES
('COMP-123', 'Salary', 15000, '2024-01-31'),
('COMP-123', 'Rent', 5000, '2024-02-01'),
('COMP-123', 'Marketing', 3000, '2024-02-15');
```

## Usage

### Via API

```bash
curl -X POST http://localhost:8000/admin/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Analyze financial performance for Q1",
    "company_id": "COMP-123",
    "analysis_period": "2024-01-01"
  }'
```

### Via Python

```python
from engine import app

result = await app.ainvoke({
    "data_store": {
        "company_id": "COMP-123",
        "analysis_period": "2024-01-01"
    }
})

report = result["data_store"]["financial_report"]
print(f"Status: {report['status']}")
print(f"Net Profit: ${report['summary']['net_profit']}")
print(f"Profit Margin: {report['metrics']['profit_margin']}")
```

## Expected Output

```json
{
  "financial_report": {
    "report_type": "Financial Analysis",
    "status": "surplus",
    "summary": {
      "total_revenue": 43000.00,
      "total_expenses": 23000.00,
      "gross_profit": 20000.00,
      "net_profit": 16000.00,
      "is_deficit": false
    },
    "metrics": {
      "profit_margin": "46.5%",
      "roi": "69.6%",
      "tax_rate": "20%"
    },
    "taxation": {
      "tax_liability": 4000.00,
      "effective_rate": 0.20,
      "description": "Tax calculated at 20% on gross profit"
    },
    "health": {
      "is_profitable": true,
      "needs_attention": false,
      "performance": "excellent"
    }
  }
}
```

## Adding LLM Reasoning (Optional)

For AI-powered analysis, use the companion `FinancialAnalyzer` skill:

```yaml
# In your workflow
steps:
  1. FinancialAnalysisPipeline (steps 1-3: fetch & merge data)
  2. FinancialAnalyzer (LLM reasoning)
  3. FinancialAnalysisPipeline continues (steps 4-5: compute & format)
```

The `FinancialAnalyzer` skill (separate) provides:
- Logical reasoning on financial data
- Business health scoring
- Strategic recommendations
- Pattern recognition

See `../FinancialAnalyzer/skill.md` for details.

## Extending the Pipeline

### Add More Data Sources

```yaml
# Add MongoDB query
- type: query
  name: fetch_customer_feedback
  source: mongodb
  collection: reviews
  filter:
    company_id: "{company_id}"
  output: feedback_data
```

### Add Transformations

```yaml
# Custom data transformation
- type: transform
  name: normalize_data
  function: normalize_financial_data
  inputs:
    - raw_financial_data
  output: normalized_data
```

### Add Caching

```yaml
# Cache expensive queries
- type: query
  name: fetch_sales
  source: postgres
  query: "..."
  cache_ttl: 3600  # Cache for 1 hour
  output: sales_data
```

## Testing

```python
# Test individual functions
from skills.FinancialAnalysisPipeline.pipeline_functions import (
    compute_financial_metrics,
    format_financial_report
)

# Mock data
test_data = {
    "sales_data": {
        "query_result": [
            {"total_revenue": 25000},
            {"total_revenue": 18000}
        ]
    },
    "expense_data": {
        "query_result": [
            {"total_expense": 15000},
            {"total_expense": 5000},
            {"total_expense": 3000}
        ]
    }
}

# Test compute
metrics = compute_financial_metrics(test_data)
assert metrics["total_revenue"] == 43000
assert metrics["total_expenses"] == 23000
assert metrics["net_profit"] == 16000
assert metrics["is_deficit"] == False

# Test format
report = format_financial_report(metrics)
assert report["status"] == "surplus"
assert report["metrics"]["profit_margin"] == "46.5%"
```

## Troubleshooting

### Function Not Found Error

```
ValueError: Transform function 'compute_financial_metrics' not found in registry
```

**Solution**: Ensure functions are registered in `engine.py`:

```python
from skills.FinancialAnalysisPipeline.pipeline_functions import compute_financial_metrics
register_action_function("compute_financial_metrics", compute_financial_metrics)
```

### Database Connection Error

```
Postgres query failed: connection refused
```

**Solution**: Check credentials in `.env`:
```env
DATABASE_URL=postgresql://user:pass@host:port/dbname
```

And ensure credential is registered:
```python
from services.credentials import register_credential

register_credential("postgres_aiven_cloud_db", {
    "type": "postgres",
    "connection_string": "postgresql://..."
})
```

### Pipeline Step Error

```
Pipeline step 1: query failed
```

**Solution**: Check query syntax and input variable formatting:
```yaml
query: |
  SELECT * FROM sales
  WHERE company_id = '{company_id}'  # ← Correct: single quotes
  # NOT: WHERE company_id = {company_id}  # ← Wrong: no quotes
```

## Performance Considerations

- **Query Optimization**: Add indexes on frequently queried columns
- **Connection Pooling**: Postgres pool size configured in `engine.py`
- **Async Execution**: All queries run asynchronously
- **Result Caching**: Consider adding cache for repeated analyses

## Next Steps

1. **Add Visualization**: Generate charts from report data
2. **Add Alerts**: Trigger notifications on deficit or low margins
3. **Add Forecasting**: Use historical data to predict trends
4. **Add Benchmarking**: Compare against industry standards
5. **Add Export**: Generate PDF/Excel reports

## Related Documentation

- [Actions Documentation](../../documentations/ACTIONS.md)
- [Data Pipeline Guide](../../actions/README.md)
- [Credential Management](../../services/credentials/README.md)
- [LLM Skills](../FinancialAnalyzer/skill.md)
