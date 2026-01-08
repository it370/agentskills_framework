# Skill-Local Actions & Scripts

## Overview

**Skill-local actions** allow skills to be **self-contained, portable, and runtime-ready**. Instead of depending on global `business_logic` modules, each skill can package its own action code and scripts within its folder.

## The Problem

### Before (Global Actions)
```
skills/
  MySkill/
    skill.md → references business_logic.my_module

business_logic/
  my_module.py → global dependency
```

**Issues:**
- ❌ Skills depend on external modules
- ❌ Can't distribute skills independently
- ❌ Must restart to add new actions
- ❌ Not marketplace-friendly

### After (Skill-Local Actions)
```
skills/
  MySkill/
    skill.md
    action.py      ← Self-contained!
    script.sh      ← Skill-specific!
```

**Benefits:**
- ✅ Drop folder = instant skill
- ✅ No external dependencies
- ✅ Runtime-ready (no restart)
- ✅ Marketplace-friendly
- ✅ Version control per skill
- ✅ Portable across environments

## Usage Patterns

### Pattern 1: Auto-Discovered Action (Recommended)

The simplest approach - omit the `module` field:

**skill.md:**
```yaml
---
name: CustomCalculator
executor: action
action:
  type: python_function
  function: calculate
  # module omitted - auto-discovers action.py
---
```

**action.py:**
```python
def calculate(x, y):
    """Skill-local calculation."""
    return {"result": x + y}
```

**What happens:**
1. Framework sees missing `module`
2. Looks for `action.py` in skill folder
3. Loads as `skills.CustomCalculator.action`
4. Registers the function automatically

### Pattern 2: Explicit Relative Module

Use a relative module path starting with `.`:

**skill.md:**
```yaml
---
name: AdvancedProcessor
executor: action
action:
  type: python_function
  function: process_data
  module: .processing  # Relative to skill folder
---
```

**processing.py:**
```python
def process_data(data):
    """Process data with advanced logic."""
    return {"processed": data * 2}
```

The framework resolves `.processing` to `skills.AdvancedProcessor.processing`.

### Pattern 3: Skill-Local Script

Use relative paths for scripts:

**skill.md:**
```yaml
---
name: ScriptRunner
executor: action
action:
  type: script
  script_path: run.py  # Relative to skill folder
  interpreter: python
---
```

**run.py:**
```python
#!/usr/bin/env python3
import sys, json

inputs = json.load(sys.stdin)
result = {"output": inputs["input"] * 2}
json.dump(result, sys.stdout)
```

The framework resolves relative paths from the skill directory.

### Pattern 4: Multiple Scripts in Skill

**skill.md:**
```yaml
---
name: MultiStepProcessor
executor: action
action:
  type: script
  script_path: steps/process.sh
  interpreter: bash
---
```

**Folder structure:**
```
MultiStepProcessor/
  ├── skill.md
  └── steps/
      ├── process.sh
      ├── validate.py
      └── transform.js
```

### Pattern 5: Multiple Functions in One Action File

**skill.md (Skill A):**
```yaml
action:
  function: calculate_risk
  # module omitted
```

**skill.md (Skill B):**
```yaml
action:
  function: calculate_premium
  # module omitted
```

**action.py (shared by both):**
```python
def calculate_risk(score):
    return {"risk": score * 0.8}

def calculate_premium(risk):
    return {"premium": risk * 1000}
```

## Auto-Discovery Rules

### For Python Functions

Framework searches in this order:

1. **action.py** - Primary convention
2. **run.py** - Alternative
3. **execute.py** - Alternative
4. **{skill_name.lower()}.py** - Name-based

Example:
```
CustomPricingCalculator/
  action.py  ← Framework finds this first
```

### For Scripts

Framework searches for common names:

1. **script.py**
2. **run.py**
3. **execute.py**
4. **script.sh**
5. **run.sh**

If `script_path` is specified, uses that directly.

## File Structure Conventions

### Minimal Skill
```
MySkill/
  ├── skill.md
  └── action.py
```

### Standard Skill
```
MySkill/
  ├── skill.md
  ├── prompt.md       # Optional prompt
  ├── action.py       # Action logic
  └── README.md       # Skill documentation
```

### Complex Skill
```
MySkill/
  ├── skill.md
  ├── action.py
  ├── script.py
  ├── utils.py        # Helper modules
  ├── config.json     # Skill configuration
  ├── tests/          # Skill-specific tests
  │   └── test_action.py
  └── docs/
      └── README.md
```

### Multi-Script Skill
```
DataPipeline/
  ├── skill.md
  ├── scripts/
  │   ├── extract.py
  │   ├── transform.py
  │   └── load.py
  └── lib/
      └── helpers.py
```

## Complete Examples

### Example 1: Self-Contained Calculator

**skills/CustomPricingCalculator/skill.md:**
```yaml
---
name: CustomPricingCalculator
requires: [base_price, quantity, customer_type]
produces: [final_price, discount_percent]
executor: action
action:
  type: python_function
  function: calculate_custom_pricing
---
```

**skills/CustomPricingCalculator/action.py:**
```python
def calculate_custom_pricing(base_price, quantity, customer_type):
    tier_discounts = {"vip": 0.20, "member": 0.10, "regular": 0.05}
    
    discount = tier_discounts.get(customer_type, 0.0)
    
    # Bulk discount
    if quantity >= 100:
        discount += 0.15
    elif quantity >= 10:
        discount += 0.05
    
    discount = min(discount, 0.50)  # Cap at 50%
    final = base_price * quantity * (1 - discount)
    
    return {
        "final_price": round(final, 2),
        "discount_percent": round(discount * 100, 2)
    }
```

**To use this skill:**
```bash
# Just drop the folder into skills/ - it works immediately!
cp -r CustomPricingCalculator/ ./skills/
# No restart needed! (in most cases)
```

### Example 2: Portable Data Transformer

**skills/DataTransformer/skill.md:**
```yaml
---
name: DataTransformer
requires: [input_data, transform_type]
produces: [transformed_data, transform_stats]
executor: action
action:
  type: script
  script_path: transform.py
  interpreter: python
---
```

**skills/DataTransformer/transform.py:**
```python
#!/usr/bin/env python3
import sys, json

def normalize(data):
    min_val, max_val = min(data), max(data)
    return [(x - min_val) / (max_val - min_val) for x in data]

inputs = json.load(sys.stdin)
result = {
    "transformed_data": normalize(inputs["input_data"]),
    "transform_stats": {"type": "normalize"}
}
json.dump(result, sys.stdout)
```

## Runtime Skill Loading

Skills can be added at runtime without restart (in most scenarios):

### Scenario 1: Hot-Reload (If Supported)

```python
from engine import load_skill_registry, SKILL_REGISTRY

# Reload skills
SKILL_REGISTRY.clear()
SKILL_REGISTRY.extend(load_skill_registry())

print(f"Loaded {len(SKILL_REGISTRY)} skills")
```

### Scenario 2: Dynamic Skill Addition

```python
from engine import register_skill_from_folder

# Add a single skill dynamically
new_skill = register_skill_from_folder("./plugins/MyNewSkill")
SKILL_REGISTRY.append(new_skill)
```

### Scenario 3: Marketplace Installation

```bash
# User downloads skill from marketplace
wget https://marketplace.example.com/skills/MySkill.zip

# Extract to skills folder
unzip MySkill.zip -d ./skills/

# Skill is automatically discovered on next run
# Or trigger hot-reload if supported
```

## Testing Skill-Local Actions

### Test Action Directly

```python
# Import skill-local action
from skills.CustomPricingCalculator.action import calculate_custom_pricing

# Test it
result = calculate_custom_pricing(
    base_price=100.0,
    quantity=50,
    customer_type="vip"
)

assert result["final_price"] < 100.0 * 50
assert result["discount_percent"] > 0
```

### Test Script Directly

```bash
# Test script with sample input
echo '{"input_data": [1, 2, 3, 4, 5], "transform_type": "normalize"}' | \
python skills/DataTransformer/transform.py

# Expected output:
# {"transformed_data": [0.0, 0.25, 0.5, 0.75, 1.0], ...}
```

### Integration Test

```python
from engine import app

# Test skill in workflow
state = {
    "layman_sop": "Test custom pricing",
    "data_store": {
        "base_price": 100.0,
        "quantity": 50,
        "customer_type": "vip"
    },
    "history": [],
    "thread_id": "test_001"
}

result = await app.ainvoke(state, {"configurable": {"thread_id": "test_001"}})
assert "final_price" in result["data_store"]
```

## Distribution & Packaging

### Package Structure

```
MySkill.zip
  ├── skill.md
  ├── action.py
  ├── README.md
  ├── LICENSE
  ├── requirements.txt  # Python dependencies
  └── tests/
      └── test_action.py
```

### Installation

```bash
# Method 1: Simple copy
unzip MySkill.zip -d ./skills/MySkill/

# Method 2: Git submodule
git submodule add https://github.com/user/MySkill skills/MySkill

# Method 3: Package manager (future)
skillpm install MySkill
```

### Versioning

**skill.md metadata:**
```yaml
---
name: CustomPricingCalculator
version: 1.2.0
author: Your Name
license: MIT
repository: https://github.com/user/CustomPricingCalculator
---
```

## Best Practices

### 1. Keep Actions Self-Contained
✅ **Good:**
```python
# action.py - All logic self-contained
def calculate(x, y):
    return {"result": x + y}
```

❌ **Avoid:**
```python
# action.py - Depends on external module
from some_external_lib import special_calc

def calculate(x, y):
    return special_calc(x, y)  # External dependency
```

### 2. Use Relative Imports for Skill Helpers

If you need multiple files:

**action.py:**
```python
from .utils import validate_input

def calculate(x, y):
    if not validate_input(x, y):
        raise ValueError("Invalid input")
    return {"result": x + y}
```

**utils.py:**
```python
def validate_input(x, y):
    return x > 0 and y > 0
```

### 3. Document Dependencies

**README.md:**
```markdown
# CustomPricingCalculator

## Dependencies
- Python 3.8+
- No external packages required

## Installation
Just copy folder to skills/ directory

## Usage
Requires: base_price, quantity, customer_type
Produces: final_price, discount_percent
```

### 4. Include Tests

**tests/test_action.py:**
```python
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from action import calculate_custom_pricing

def test_vip_discount():
    result = calculate_custom_pricing(100.0, 10, "vip")
    assert result["discount_percent"] > 20.0

def test_bulk_discount():
    result = calculate_custom_pricing(100.0, 100, "regular")
    assert result["discount_percent"] > 15.0
```

### 5. Handle Errors Gracefully

```python
def calculate_custom_pricing(base_price, quantity, customer_type):
    # Validate inputs
    if base_price <= 0:
        raise ValueError("base_price must be positive")
    
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    
    # Handle unknown customer types gracefully
    tier_discounts = {"vip": 0.20, "member": 0.10, "regular": 0.05}
    discount = tier_discounts.get(customer_type.lower(), 0.0)
    
    # ... rest of logic
```

## Troubleshooting

### Issue: "Function not found"

**Problem:**
```
RuntimeError: Function 'my_function' not found in module 'skills.MySkill.action'
```

**Solutions:**
1. Check function name matches skill.md
2. Ensure action.py exists in skill folder
3. Verify function is defined (not just declared)
4. Check for syntax errors in action.py

### Issue: "Module import failed"

**Problem:**
```
ImportError: No module named 'skills.MySkill.action'
```

**Solutions:**
1. Ensure action.py exists
2. Check file permissions
3. Verify Python can import from skills/
4. Check for `__init__.py` if using packages

### Issue: "Script not found"

**Problem:**
```
FileNotFoundError: Script not found: ./scripts/process.py
```

**Solutions:**
1. Check script_path in skill.md
2. Ensure script file exists in skill folder
3. Use forward slashes even on Windows
4. Make script executable on Unix: `chmod +x script.py`

## Comparison: Global vs Local Actions

| Aspect | Global Actions | Skill-Local Actions |
|--------|---------------|---------------------|
| **Location** | business_logic/ | skills/SkillName/ |
| **Reusability** | Across all skills | Single skill |
| **Portability** | Requires module | Self-contained |
| **Distribution** | Separate package | With skill |
| **Runtime Add** | Needs restart | Hot-reload friendly |
| **Testing** | Separate tests | In skill folder |
| **Versioning** | Global version | Per-skill version |

**When to use each:**

- **Global actions**: Shared business logic used by multiple skills
- **Skill-local actions**: Skill-specific logic, portable skills, marketplace skills

## Migration: Global → Local

### Before (Global):

**business_logic/custom.py:**
```python
def calculate(x, y):
    return {"result": x + y}
```

**skills/MySkill/skill.md:**
```yaml
action:
  type: python_function
  module: business_logic.custom
  function: calculate
```

### After (Local):

**skills/MySkill/action.py:**
```python
def calculate(x, y):
    return {"result": x + y}
```

**skills/MySkill/skill.md:**
```yaml
action:
  type: python_function
  function: calculate
  # module omitted
```

**Benefits:**
- ✅ Self-contained
- ✅ Portable
- ✅ No global dependencies

## Future: Skill Marketplace

Skill-local actions enable a marketplace ecosystem:

```python
# Install from marketplace
from marketplace import SkillMarketplace

market = SkillMarketplace()
market.install("CustomPricingCalculator", version="1.2.0")

# Skill downloaded to: skills/CustomPricingCalculator/
# Automatically loaded and ready to use!
```

## Summary

Skill-local actions transform skills from **configuration** into **portable packages**:

- ✅ **Drop folder = instant skill**
- ✅ **No external dependencies**
- ✅ **Runtime-ready**
- ✅ **Marketplace-friendly**
- ✅ **Version control per skill**
- ✅ **Self-documented**
- ✅ **Easy testing**

This is a **game-changer** for skill distribution, plugin systems, and marketplace ecosystems!

## See Also

- [ACTIONS_README.md](./ACTIONS_README.md) - Complete action system docs
- [QUICKSTART_ACTIONS.md](./QUICKSTART_ACTIONS.md) - Quick start guide
- [skills/CustomPricingCalculator/](./skills/CustomPricingCalculator/) - Example skill-local action
- [skills/DataTransformer/](./skills/DataTransformer/) - Example skill-local script
