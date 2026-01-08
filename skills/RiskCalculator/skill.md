---
name: RiskCalculator
description: Calculate financial risk score using business rules (deterministic calculation)
requires:
  - credit_score
  - income
  - debt
  - employment_years
produces:
  - risk_score
  - risk_tier
  - recommendation
executor: action

action:
  type: python_function
  module: business_logic
  function: calculate_risk_score
  timeout: 5.0
---

# RiskCalculator

## Purpose
Calculate financial risk score using weighted components based on:
- Credit score (40% weight)
- Income level (30% weight)
- Debt-to-income ratio (20% weight)
- Employment history (10% weight)

This is a deterministic calculation that doesn't require LLM inference.

## Business Rules

### Risk Tiers
- **Low Risk (80-100)**: Approve automatically
- **Medium Risk (60-79)**: Manual review required
- **High Risk (0-59)**: Deny or require additional verification

### Scoring Components
1. **Credit Score**: Normalized to 0-40 scale (credit_score / 850 * 40)
2. **Income**: Capped at 30 points for $100k+ income
3. **Debt Ratio**: 20 points minus penalty for high debt-to-income ratio
4. **Employment**: 2 points per year, capped at 10 points

## Output Schema
- `risk_score`: Float (0-100)
- `risk_tier`: String ("low_risk", "medium_risk", "high_risk")
- `recommendation`: String ("approve", "manual_review", "deny")

## Example
Input:
```json
{
  "credit_score": 750,
  "income": 75000,
  "debt": 15000,
  "employment_years": 5
}
```

Output:
```json
{
  "risk_score": 82.35,
  "risk_tier": "low_risk",
  "recommendation": "approve"
}
```

