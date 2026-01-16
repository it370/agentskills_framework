---
name: LoanTermsCalculator
description: Calculate loan terms including interest rate and monthly payments
requires:
  - loan_amount
  - risk_tier
  - credit_score
produces:
  - interest_rate
  - monthly_payment
  - term_months
  - total_interest
executor: action

action:
  type: python_function
  module: business_logic
  function: calculate_loan_terms
  timeout: 5.0
---

# LoanTermsCalculator

## Purpose
Calculate loan terms based on risk assessment and credit profile.
This is a pure calculation that doesn't require LLM inference.

## Business Rules

### Base Interest Rates by Risk Tier
- Low Risk: 3.5% APR
- Medium Risk: 6.5% APR  
- High Risk: 12.0% APR

### Credit Score Adjustments
- 800+: -0.5% rate adjustment
- 750-799: No adjustment
- 700-749: +0.5% adjustment
- <700: +1.0% adjustment

### Loan Terms by Amount
- < $10,000: 24 months
- $10,000 - $49,999: 60 months
- $50,000+: 84 months

## Output Schema
- `interest_rate`: Annual percentage rate
- `monthly_payment`: Monthly payment amount
- `term_months`: Loan term in months
- `total_interest`: Total interest paid over loan life
