---
name: FinancialAnalyzer
description: |
  AI-powered financial analyst that performs logical reasoning on sales and expense data.
  Provides business insights, health scoring, and strategic recommendations.

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
  You are an expert financial analyst. Analyze the following business financial data and provide comprehensive insights.
  
  ## Sales Data
  {raw_financial_data.sales_data.query_result}
  
  ## Expense Data
  {raw_financial_data.expense_data.query_result}
  
  ## Your Task
  Perform logical reasoning and financial analysis to calculate and determine:
  
  1. **is_deficit** (boolean): Is the business in deficit? (expenses > revenue)
  2. **total_amount** (number): Total revenue generated from all sales
  3. **total_profit** (number): Net profit (revenue - expenses)
  4. **gross_income** (number): Total gross income before any deductions
  5. **business_health_score** (0-100): Overall business health score considering:
     - Profitability
     - Expense management
     - Revenue diversity
     - Growth potential
  6. **recommendations** (array of strings): 3-5 actionable business recommendations
  
  ## Scoring Guidelines
  - Score 80-100: Excellent financial health, strong profitability
  - Score 60-79: Good health, some areas for improvement
  - Score 40-59: Fair health, attention needed
  - Score 0-39: Poor health, urgent action required
  
  ## Response Format
  Return ONLY valid JSON with these exact keys (no markdown, no explanation):
  
  {
    "is_deficit": boolean,
    "total_amount": number,
    "total_profit": number,
    "gross_income": number,
    "business_health_score": number,
    "recommendations": [string, string, string]
  }

system_prompt: |
  You are a precise financial analyst AI. You must:
  1. Analyze financial data accurately
  2. Perform mathematical calculations correctly
  3. Provide actionable business insights
  4. Return responses in valid JSON format only
  5. Base recommendations on data-driven insights

---

# Financial Analyzer (LLM Skill)

This skill uses AI reasoning to analyze financial data and provide business intelligence.

## Purpose

While data pipeline skills handle data retrieval and computation, this LLM skill provides:
- **Logical Reasoning**: Understanding business context beyond numbers
- **Pattern Recognition**: Identifying trends and anomalies
- **Strategic Insights**: Actionable recommendations based on data
- **Health Scoring**: Holistic business performance assessment

## Input Format

Expects `raw_financial_data` with structure:
```json
{
  "sales_data": {
    "query_result": [
      {
        "product_id": 1,
        "product_name": "Widget A",
        "units_sold": 500,
        "total_revenue": 25000
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
      }
    ],
    "row_count": 3
  }
}
```

## Output Format

Produces 6 separate keys in data_store:
```json
{
  "is_deficit": false,
  "total_amount": 43000.00,
  "total_profit": 20000.00,
  "gross_income": 43000.00,
  "business_health_score": 78,
  "recommendations": [
    "Increase marketing spend for Widget A (highest revenue generator)",
    "Review salary expenses - represents 65% of total costs",
    "Consider diversifying product line to reduce revenue concentration risk"
  ]
}
```

## Usage in Workflow

### Standalone
```python
# Prepare data (from previous pipeline or queries)
data = {
    "raw_financial_data": {
        "sales_data": {...},
        "expense_data": {...}
    }
}

# Run analyzer
result = await workflow.run(data)
print(f"Health Score: {result['business_health_score']}/100")
print(f"Status: {'Deficit' if result['is_deficit'] else 'Surplus'}")
```

### Combined with Pipeline
Create a workflow that chains:
1. `FinancialAnalysisPipeline` (data queries + merge)
2. `FinancialAnalyzer` (this skill - AI reasoning)
3. `FinancialAnalysisPipeline` continues (math computations + formatting)

## Example Reasoning Process

### Input Data
- Sales: $43,000 from 2 products
- Expenses: $23,000 across 3 categories

### AI Analysis
1. **Deficit Check**: Revenue ($43k) > Expenses ($23k) → No deficit ✓
2. **Profit Calculation**: $43k - $23k = $20k profit
3. **Health Score Reasoning**:
   - Profitability: Strong (46.5% margin) → +30 points
   - Expense Management: Moderate (salary-heavy) → +20 points
   - Revenue Diversity: Limited (2 products) → +15 points
   - Growth Indicators: Need more data → +13 points
   - **Total: 78/100** (Good Health)
4. **Recommendations**:
   - Focus on top performer (Widget A)
   - Optimize largest expense (Salary)
   - Diversify revenue streams

## Integration Example

### Full Financial Analysis Workflow
```yaml
# workflow.yaml
steps:
  # Step 1: Get raw data
  - skill: FinancialDataRetriever
    outputs: [sales_raw, expense_raw]
  
  # Step 2: AI reasoning
  - skill: FinancialAnalyzer
    inputs:
      raw_financial_data:
        sales_data: sales_raw
        expense_data: expense_raw
    outputs: [is_deficit, total_profit, business_health_score, recommendations]
  
  # Step 3: Advanced computations
  - skill: TaxAndReportGenerator
    inputs: [total_profit, is_deficit]
    outputs: [final_report]
```

## Why Use LLM for This?

**Advantages over pure computation:**
- **Context Understanding**: Recognizes industry patterns
- **Qualitative Analysis**: Beyond just numbers
- **Natural Language Output**: Human-readable recommendations
- **Adaptive Reasoning**: Handles varying data structures
- **Insight Generation**: Discovers non-obvious patterns

**When to use computation instead:**
- Fixed formulas (tax calculation)
- High-precision math (financial regulations)
- Performance-critical operations
- Deterministic outputs required

## Testing

```python
# Test with sample data
test_data = {
    "raw_financial_data": {
        "sales_data": {
            "query_result": [
                {"product_name": "Widget A", "total_revenue": 25000},
                {"product_name": "Widget B", "total_revenue": 18000}
            ]
        },
        "expense_data": {
            "query_result": [
                {"expense_category": "Salary", "total_expense": 15000},
                {"expense_category": "Rent", "total_expense": 5000},
                {"expense_category": "Marketing", "total_expense": 3000}
            ]
        }
    }
}

# Expected output:
# is_deficit: False (43k revenue > 23k expenses)
# total_profit: 20000
# business_health_score: 75-85 (good profitability, expense management needed)
```

## Prompt Engineering Notes

The prompt is carefully structured to:
1. **Set context**: "You are an expert financial analyst"
2. **Provide data**: Clear formatting of sales/expense data
3. **Define task**: Specific calculations and reasoning required
4. **Give guidelines**: Scoring criteria for health score
5. **Enforce format**: JSON-only output with exact keys
6. **System prompt**: Reinforces precision and format requirements

## Related Skills

- **FinancialAnalysisPipeline**: Complete pipeline including this analyzer
- **TaxCalculator**: Specialized tax computation
- **RevenueForecaster**: Predictive analysis based on historical data
- **ExpenseOptimizer**: AI-powered cost reduction recommendations
