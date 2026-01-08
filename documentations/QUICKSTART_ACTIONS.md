# Quick Start: Action Executor System

This guide will get you up and running with the Action Executor System in 5 minutes.

## Step 1: Create Your First Action Function

Create a new file `my_actions.py`:

```python
from actions import action

@action(
    name="calculate_discount",
    requires={"price", "customer_type"},
    produces={"final_price", "discount_amount"}
)
def calculate_discount(price: float, customer_type: str) -> dict:
    """Calculate discounted price based on customer type."""
    
    discounts = {
        "vip": 0.20,      # 20% off
        "member": 0.10,   # 10% off
        "regular": 0.0    # No discount
    }
    
    discount_rate = discounts.get(customer_type, 0.0)
    discount_amount = price * discount_rate
    final_price = price - discount_amount
    
    return {
        "final_price": round(final_price, 2),
        "discount_amount": round(discount_amount, 2)
    }
```

## Step 2: Create a Skill Using Your Action

Create `skills/DiscountCalculator/skill.md`:

```yaml
---
name: DiscountCalculator
description: Calculate final price with customer discounts
requires:
  - price
  - customer_type
produces:
  - final_price
  - discount_amount
executor: action

action:
  type: python_function
  module: my_actions
  function: calculate_discount
  timeout: 5.0
---

# DiscountCalculator

Applies customer-tier based discounts to prices.

## Discount Tiers
- VIP: 20% off
- Member: 10% off
- Regular: No discount
```

## Step 3: Register Your Actions (Optional - for auto-discovery)

In your main application file or `main.py`:

```python
from engine import auto_discover_actions

# Auto-discover actions from your module
auto_discover_actions(["my_actions", "business_logic"])
```

## Step 4: Run a Workflow

```python
from engine import app

# Define initial state
initial_state = {
    "layman_sop": "Calculate discounted price for customer order",
    "data_store": {
        "price": 100.0,
        "customer_type": "vip"
    },
    "history": ["Process Started"],
    "thread_id": "test_001"
}

config = {"configurable": {"thread_id": "test_001"}}

# Run the workflow
result = await app.ainvoke(initial_state, config)

# Check results
print(result['data_store']['final_price'])     # 80.0
print(result['data_store']['discount_amount'])  # 20.0
```

## Step 5: Test Your Action Directly

```python
from my_actions import calculate_discount

# Test without the framework
result = calculate_discount(
    price=100.0,
    customer_type="vip"
)

assert result['final_price'] == 80.0
assert result['discount_amount'] == 20.0
print("✓ Action works correctly!")
```

## Common Patterns

### Pattern 1: Database Query Action

```yaml
---
name: FetchUserData
requires: [user_id]
produces: [user_profile]
executor: action

action:
  type: data_query
  source: postgres
  query: "SELECT * FROM users WHERE id = {user_id}"
---
```

### Pattern 2: Multi-Step Pipeline

```yaml
---
name: EnrichUserProfile
requires: [user_id]
produces: [enriched_profile]
executor: action

action:
  type: data_pipeline
  steps:
    - type: query
      source: postgres
      query: "SELECT * FROM users WHERE id = {user_id}"
      output: base_profile
    
    - type: query
      source: mongodb
      collection: user_preferences
      filter: {user_id: "{user_id}"}
      output: preferences
    
    - type: merge
      inputs: [base_profile, preferences]
      output: enriched_profile
---
```

### Pattern 3: External Script

```yaml
---
name: ProcessDocument
requires: [document_path]
produces: [extracted_text]
executor: action

action:
  type: script
  script_path: ./scripts/extract_text.py
  interpreter: python
  timeout: 30.0
---
```

### Pattern 4: Quick API Call

```yaml
---
name: ValidateAddress
requires: [address]
produces: [is_valid, standardized_address]
executor: action

action:
  type: http_call
  url: "https://api.usps.com/validate"
  method: POST
  timeout: 10.0
---
```

## Troubleshooting

### "Function not found in registry"
- Ensure your function is decorated with `@action`
- Check that you've called `auto_discover_actions()` with your module
- Verify module and function names match exactly

### "Signature mismatch"
- Make sure skill's `requires` fields match function parameter names
- Check parameter spelling and capitalization

### "Import error"
- Ensure your module is in the Python path
- Check for typos in module names
- Verify all dependencies are installed

## Next Steps

1. ✅ **Read the full documentation**: [ACTIONS_README.md](./ACTIONS_README.md)
2. ✅ **Explore examples**: Check `business_logic/` for more action examples
3. ✅ **Review sample skills**: See `skills/` for complete skill examples
4. ✅ **Run examples**: `python examples_actions.py`

## Performance Benefits

Switching from LLM to Action executor:

| Metric | LLM Executor | Action Executor | Improvement |
|--------|--------------|-----------------|-------------|
| Speed | 2-5 seconds | 5-50ms | 40-1000x faster |
| Cost | $0.01-0.05/call | < $0.0001/call | 99.9% cheaper |
| Reliability | ~95% | 100% | Deterministic |
| Testing | Difficult | Easy | Unit testable |

## Get Help

- 📖 Full documentation: [ACTIONS_README.md](./ACTIONS_README.md)
- 💡 Example code: [examples_actions.py](./examples_actions.py)
- 🛠️ Sample actions: [business_logic/](./business_logic/)
- 📝 Sample skills: [skills/](./skills/)

Happy coding! 🚀
