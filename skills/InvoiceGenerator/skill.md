---
name: InvoiceGenerator
description: Generate invoice with line items, discounts, and tax calculations
requires:
  - order_items
  - tax_rate
  - customer_tier
produces:
  - invoice_total
  - discount_applied
  - line_items
  - tax_amount
executor: action

action:
  type: python_function
  module: business_logic
  function: generate_invoice
  timeout: 5.0
---

# InvoiceGenerator

## Purpose
Generate a complete invoice with line-item calculations, tier-based discounts, and tax.

## Business Rules

### Customer Tier Discounts
- **Premium**: 15% discount
- **Standard**: 5% discount
- **Basic**: No discount

### Calculation Order
1. Calculate line item subtotals (price × quantity)
2. Sum to get order subtotal
3. Apply tier-based discount
4. Calculate tax on discounted amount
5. Final total = subtotal - discount + tax

## Input Format
```json
{
  "order_items": [
    {"name": "Product A", "price": 100.00, "quantity": 2},
    {"name": "Product B", "price": 50.00, "quantity": 1}
  ],
  "tax_rate": 0.08,
  "customer_tier": "premium"
}
```

## Output Schema
- `invoice_total`: Final total after discount and tax
- `discount_applied`: Dollar amount of discount
- `line_items`: List with calculated subtotals per item
- `tax_amount`: Tax amount charged
