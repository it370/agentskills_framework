---
name: CustomPricingCalculator
description: Calculate custom pricing with skill-local business logic
requires:
  - base_price
  - quantity
  - customer_type
produces:
  - final_price
  - discount_percent
  - bulk_discount
executor: action

action:
  type: python_function
  function: calculate_custom_pricing
  # module omitted - will auto-discover action.py in this folder
---

# CustomPricingCalculator

## Purpose
Demonstrates a **self-contained skill** with its own action code.

The action logic is in `action.py` in the same folder, making this skill:
- ✅ Portable (copy folder = copy skill)
- ✅ Self-contained (no global dependencies)
- ✅ Runtime-ready (can be added without restart)
- ✅ Marketplace-friendly (package and distribute)

## Business Rules
- Bulk discounts for quantities > 10
- Customer-tier based pricing
- Volume-based discounts

## Skill Structure
```
CustomPricingCalculator/
  ├── skill.md          # This file
  └── action.py         # Skill-specific logic
```

When `module` is omitted from action config, the framework automatically:
1. Looks for `action.py` in the skill folder
2. Dynamically loads it as `skills.{SkillName}.action`
3. Registers the specified function

This allows skills to be dropped into the `skills/` folder at runtime!
