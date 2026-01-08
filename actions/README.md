# Actions Module

This folder contains action-related utilities and examples for the agent skills framework.

## Contents

### `__init__.py` - Core Actions Module
The main actions module with decorators and utilities:

- **`@action` decorator** - Mark functions as actions
- **`validate_action_result()`** - Validate action outputs
- **`create_skill_from_action()`** - Generate skill metadata from functions
- **`sync_action()`** - Async wrapper for sync functions
- **`data_action()`** - Decorator for data-fetching actions

### `examples.py` - Usage Examples
Runnable examples demonstrating:
- Action registration
- Auto-discovery
- Direct testing
- Performance comparisons
- Workflow execution
- Data pipeline simulation

Run it with: `python -m actions.examples`

## Quick Start

### 1. Import the decorator
```python
from actions import action
```

### 2. Create an action
```python
@action(
    name="calculate_total",
    requires={"price", "quantity"},
    produces={"total"}
)
def calculate_total(price, quantity):
    return {"total": price * quantity}
```

### 3. Use in a skill
```yaml
---
name: TotalCalculator
executor: action
action:
  type: python_function
  module: my_module
  function: calculate_total
---
```

## Utilities

### validate_action_result()
```python
from actions import validate_action_result

result = {"output": 42}
validate_action_result(result, {"output"}, "MyAction")
# Raises ValueError if output keys missing
```

### create_skill_from_action()
```python
from actions import create_skill_from_action, action

@action(requires={"x", "y"}, produces={"sum"})
def add(x, y):
    return {"sum": x + y}

skill_meta = create_skill_from_action(add)
# Returns complete skill metadata dict
```

## Examples

See `examples.py` for complete, runnable examples of:
- ✅ Simple action registration
- ✅ Auto-discovery setup
- ✅ Listing action skills
- ✅ Testing actions directly
- ✅ Running workflows
- ✅ Performance comparisons
- ✅ Data pipeline simulations

## See Also

- **`/business_logic`** - Example action implementations
- **`/skills`** - Example action-based skills
- **`/documentations`** - Complete documentation
- **`/engine.py`** - Core framework

## Architecture

```
actions/
  ├── __init__.py     # Core decorators & utilities
  ├── examples.py     # Runnable examples
  └── README.md       # This file

business_logic/
  ├── __init__.py     # Reusable action functions
  └── data_processing.py

skills/
  ├── RiskCalculator/
  │   └── skill.md    # Uses business_logic actions
  └── CustomPricing/
      ├── skill.md
      └── action.py   # Skill-local action
```

## Import Patterns

### Framework Code
```python
from actions import action, validate_action_result
```

### User Code
```python
from actions import action

@action(requires={"x"}, produces={"y"})
def my_function(x):
    return {"y": x * 2}
```

### Engine Integration
```python
from engine import register_action_function, auto_discover_actions

# Manual registration
register_action_function("my_module.my_func", my_func)

# Auto-discovery
auto_discover_actions(["business_logic", "my_module"])
```

## Testing

```python
# Test action decorator
from actions import action

@action(requires={"x"}, produces={"result"})
def double(x):
    return {"result": x * 2}

assert double(5) == {"result": 10}
assert hasattr(double, '_is_action')
assert double._requires == {"x"}
```

## Best Practices

1. **Use descriptive names**
   ```python
   @action(name="calculate_shipping_cost", ...)
   ```

2. **Specify clear contracts**
   ```python
   @action(
       requires={"weight", "distance"},
       produces={"cost", "estimated_days"}
   )
   ```

3. **Document your functions**
   ```python
   @action(...)
   def calculate(x, y):
       """Calculate something useful."""
       return {"result": x + y}
   ```

4. **Keep actions pure**
   - No side effects
   - Deterministic outputs
   - Clear input/output contracts

5. **Test independently**
   ```python
   from my_module import my_action
   result = my_action(input_data)
   assert result["output"] == expected
   ```

## Troubleshooting

### "Module 'actions' has no attribute 'action'"
**Solution:** Import from the package:
```python
from actions import action  # ✓ Correct
# not: import actions.action
```

### "Function signature mismatch"
**Solution:** Ensure function parameters match `requires`:
```python
@action(requires={"x", "y"}, ...)
def func(x, y):  # Parameters match requires
    ...
```

### "Auto-register failed"
**Solution:** This is normal if engine not loaded yet. Use `auto_discover_actions()` in main.py:
```python
from engine import auto_discover_actions
auto_discover_actions(["my_module"])
```

## Contributing

When adding new utilities to this module:
1. Add docstrings with examples
2. Add tests
3. Update this README
4. Add to `examples.py` if applicable
