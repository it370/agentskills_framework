# Quick Start: Financial Analysis Pipeline

## What This Example Shows

✅ Multiple PostgreSQL queries in one pipeline  
✅ Data merging from different sources  
✅ Python mathematical computations  
✅ Proper `produces` key mapping  
✅ No key conflicts between skills  

## File Structure

```
skills/FinancialAnalysisPipeline/
├── skill.md              # Main pipeline definition
├── pipeline_functions.py # Python computation functions
├── test_pipeline.py      # Standalone function tests
├── README.md            # Complete documentation
├── EXAMPLE_SUMMARY.md   # Implementation details
└── QUICK_START.md       # This file
```

## Pipeline Steps

1. **Query Sales**: `SELECT * FROM sales WHERE company_id = '{company_id}'`
2. **Query Expenses**: `SELECT * FROM expenses WHERE company_id = '{company_id}'`
3. **Merge Data**: Combine both query results
4. **Compute Metrics**: Calculate profit, tax (20%), margins, ROI
5. **Format Report**: Structure into report with sections

## Test Without Database

```bash
cd skills/FinancialAnalysisPipeline
python test_pipeline.py
```

Expected output:
```
============================================================
  FinancialAnalysisPipeline Function Tests
============================================================

=== Testing compute_financial_metrics ===
✓ All assertions passed
  Total Revenue: $43,000.00
  Total Expenses: $23,000.00
  Gross Profit: $20,000.00
  Tax Liability (20%): $4,000.00
  Net Profit: $16,000.00
  Profit Margin: 46.5%
  ROI: 69.6%
  Status: Surplus

=== Testing format_financial_report ===
✓ All assertions passed
  Report Type: Financial Analysis
  Status: surplus
  Profit Margin: 46.5%
  ROI: 69.6%
  Tax Rate: 20%
  Performance: excellent

============================================================
  ✓ ALL TESTS PASSED
============================================================
```

## Run With Database

### 1. Setup Database

```sql
-- Run this SQL
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
    expense_date DATE
);

-- Insert sample data
INSERT INTO sales VALUES
(1, 'COMP-123', 1, 'Widget A', 500, 50.00, '2024-01-15'),
(2, 'COMP-123', 2, 'Widget B', 300, 60.00, '2024-02-10');

INSERT INTO expenses VALUES
(1, 'COMP-123', 'Salary', 15000, '2024-01-31'),
(2, 'COMP-123', 'Rent', 5000, '2024-02-01'),
(3, 'COMP-123', 'Marketing', 3000, '2024-02-15');
```

### 2. Configure Credentials

```env
# .env
DATABASE_URL=postgresql://user:pass@host:port/dbname
```

### 3. Start Server

```bash
uvicorn api.main:api --reload
```

### 4. Run Skill

```bash
curl -X POST http://localhost:8000/admin/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Analyze financial performance",
    "company_id": "COMP-123",
    "analysis_period": "2024-01-01"
  }'
```

### 5. Check Results

```json
{
  "data_store": {
    "financial_report": {
      "status": "surplus",
      "summary": {
        "total_revenue": 43000,
        "total_expenses": 23000,
        "net_profit": 16000,
        "is_deficit": false
      },
      "metrics": {
        "profit_margin": "46.5%",
        "roi": "69.6%"
      }
    }
  }
}
```

## Key Concepts

### Single `produces` Key

```yaml
produces:
  - financial_report  # Only 1 key
```

**Result**: Entire pipeline output goes under this one key.

```python
# Instead of:
data_store = {
  "total_revenue": 43000,
  "total_expenses": 23000,
  "net_profit": 16000
}

# You get:
data_store = {
  "financial_report": {  # ← Everything nested under this
    "summary": {...},
    "metrics": {...},
    "taxation": {...}
  }
}
```

### Multiple Queries

Each query has its own output key:

```yaml
- type: query
  output: sales_data    # ← First query result

- type: query
  output: expense_data  # ← Second query result
```

They don't overwrite each other!

### Function Calls

Functions are called by name:

```yaml
- type: function
  function: compute_financial_metrics  # ← Must be registered
  inputs:
    - raw_financial_data
  output: computed_metrics
```

Registration happens in `engine.py`:
```python
register_action_function("compute_financial_metrics", compute_financial_metrics)
```

## Common Issues

### "Function not found"
```
ValueError: Transform function 'compute_financial_metrics' not found
```

**Fix**: Check `engine.py` has the registration code at the bottom.

### "Connection refused"
```
Postgres query failed: connection refused
```

**Fix**: Verify `DATABASE_URL` in `.env` and database is running.

### "produces key not working"
```
Expected 'financial_report' but got 'query_result'
```

**Fix**: This was the original bug! Ensure you have the latest `engine.py` with the result mapping fix (lines 766-800).

## Next Actions

1. ✅ Test functions: `python test_pipeline.py`
2. ⬜ Setup database with sample data
3. ⬜ Configure credentials in `.env`
4. ⬜ Start server and run skill
5. ⬜ Customize for your use case

## Learn More

- **Complete Docs**: See `README.md`
- **Implementation Details**: See `EXAMPLE_SUMMARY.md`
- **Actions Guide**: See `documentations/ACTIONS.md`
- **Credential Setup**: See `services/credentials/README.md`

## Support

If you encounter issues:
1. Check error messages in logs
2. Verify database connection
3. Ensure functions are registered
4. Test functions standalone first
5. Check that `produces` mapping is working

---

**Created**: 2026-01-09  
**Status**: Ready to use  
**Dependencies**: PostgreSQL, Python 3.8+, psycopg library
