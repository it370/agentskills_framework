# Action Executor System

## Overview

The Action Executor System extends the agent skills framework with deterministic, framework-driven execution capabilities. Unlike LLM-driven tools (where the LLM decides what to call), actions are executed directly by the framework based on the planner's decisions.

## Architecture: Three Execution Modes

### 1. LLM Executor (`executor: "llm"`)
- **Who decides**: LLM generates outputs
- **When to use**: Complex reasoning, natural language processing, creative tasks
- **Cost**: High (LLM inference required)
- **Example**: Analyzing candidate responses, writing emails, decision-making

### 2. REST Executor (`executor: "rest"`)
- **Who decides**: Framework dispatches to external service
- **When to use**: Long-running async operations, external agent coordination
- **Cost**: Medium (external service cost + callback overhead)
- **Example**: Background checks, third-party verification services

### 3. Action Executor (`executor: "action"`) ⭐ NEW
- **Who decides**: Framework executes deterministically
- **When to use**: Calculations, data fetching, transformations, scripts
- **Cost**: Low (no LLM, no external calls)
- **Example**: Risk calculations, database queries, file processing

## Action Types

### 1. Python Function (`type: "python_function"`)
Execute pure Python functions with business logic.

```yaml
executor: action
action:
  type: python_function
  module: business_logic
  function: calculate_risk_score
  timeout: 5.0
```

**Use cases:**
- Business calculations
- Data validation
- Algorithm execution
- Pure logic operations

**Benefits:**
- Fast execution
- Easy to test
- Type-safe
- Reusable across skills

### 2. Data Query (`type: "data_query"`)
Direct database queries (PostgreSQL, MongoDB, Redis).

```yaml
executor: action
action:
  type: data_query
  source: postgres
  query: "SELECT * FROM users WHERE id = {user_id}"
  timeout: 10.0
```

**Supported sources:**
- `postgres`: PostgreSQL queries
- `mongodb`: MongoDB queries (collection + filter)
- `redis`: Redis operations (coming soon)

**Benefits:**
- No LLM overhead for data fetching
- Automatic connection pooling
- Parameterized queries (SQL injection safe)
- Direct data access

### 3. Data Pipeline (`type: "data_pipeline"`)
Multi-step data operations with transformations.

```yaml
executor: action
action:
  type: data_pipeline
  steps:
    - type: query
      source: postgres
      query: "SELECT * FROM candidates WHERE id = {candidate_id}"
      output: candidate_data
    
    - type: query
      source: mongodb
      collection: documents
      filter: {candidate_id: "{candidate_id}"}
      output: documents
    
    - type: merge
      inputs: [candidate_data, documents]
      output: enriched_profile
```

**Step types:**
- `query`: Execute a data query
- `transform`: Apply a transformation function
- `merge`: Deep merge multiple data sources

**Benefits:**
- Atomic operations
- Guaranteed execution order
- Multiple data sources in one skill
- Automatic error handling

### 4. Script (`type: "script"`)
Execute external scripts in any language.

```yaml
executor: action
action:
  type: script
  script_path: ./scripts/parse_document.py
  interpreter: python
  timeout: 60.0
```

**Interface:**
- Input: JSON via stdin
- Output: JSON via stdout
- Exit code: 0 = success, non-zero = error

**Use cases:**
- Legacy code integration
- Language-specific processing (R, Julia, Go)
- System commands
- File operations
- Heavy computation

### 5. HTTP Call (`type: "http_call"`)
Synchronous REST API calls (< 30 seconds).

```yaml
executor: action
action:
  type: http_call
  url: "https://api.example.com/validate/{document_id}"
  method: GET
  timeout: 15.0
  headers:
    Authorization: "Bearer {api_key}"
```

**Difference from REST executor:**
- **http_call**: Synchronous, returns immediately, no callback needed
- **REST executor**: Asynchronous, uses callbacks, for long-running tasks

**Use cases:**
- Quick API lookups
- Real-time validation
- Synchronous integrations
- Data enrichment

## Creating Actions

### Method 1: Using @action Decorator

```python
# business_logic/my_actions.py
from actions import action

@action(
    name="calculate_shipping",
    requires={"weight_kg", "distance_km", "service_level"},
    produces={"shipping_cost", "estimated_days"}
)
def calculate_shipping_cost(weight_kg, distance_km, service_level):
    """Calculate shipping cost based on weight and distance."""
    base = 5.0 + (weight_kg * 0.5) + (distance_km * 0.1)
    
    multipliers = {'express': 2.0, 'standard': 1.0, 'economy': 0.7}
    cost = base * multipliers.get(service_level, 1.0)
    
    return {
        "shipping_cost": round(cost, 2),
        "estimated_days": 1 if service_level == 'express' else 3
    }
```

### Method 2: Skill YAML Configuration

```yaml
---
name: ShippingCalculator
requires: [weight_kg, distance_km, service_level]
produces: [shipping_cost, estimated_days]
executor: action

action:
  type: python_function
  module: business_logic.my_actions
  function: calculate_shipping_cost
---
```

### Method 3: Direct Registration

```python
from engine import register_action_function

def my_custom_function(x, y):
    return {"sum": x + y}

register_action_function("my_module.my_custom_function", my_custom_function)
```

## Auto-Discovery

Enable automatic discovery of @action decorated functions:

```python
# In engine.py or main.py
from engine import auto_discover_actions

# Discover all actions in these modules
auto_discover_actions([
    "business_logic",
    "business_logic.data_processing",
    "custom_actions"
])
```

## Best Practices

### When to Use Each Executor Type

| Task | Executor | Reason |
|------|----------|--------|
| Risk calculation | `action` (python_function) | Pure logic, deterministic |
| Writing personalized email | `llm` | Requires creativity, context |
| Background check | `rest` | Long-running, external service |
| Database query | `action` (data_query) | Direct data access |
| Document parsing | `action` (script) | File processing |
| Quick API lookup | `action` (http_call) | Synchronous, < 15s |
| Multi-source data | `action` (data_pipeline) | Complex data operations |

### Action Design Principles

1. **Pure Functions**: Actions should be stateless and idempotent
2. **Clear Contracts**: Define clear input/output schemas
3. **Error Handling**: Return errors in structured format, don't raise
4. **Timeout Awareness**: Set appropriate timeouts for operations
5. **Resource Management**: Use connection pools, don't create new connections
6. **Logging**: Use framework logging for observability

### Example: Well-Designed Action

```python
@action(
    name="validate_application",
    requires={"application_id", "required_fields"},
    produces={"is_valid", "missing_fields", "validation_errors"}
)
def validate_application(application_id, required_fields):
    """
    Validate application completeness.
    
    Returns validation status with detailed error information.
    """
    try:
        # Fetch application data
        app = get_application(application_id)
        
        # Check required fields
        missing = []
        errors = []
        
        for field in required_fields:
            if field not in app or not app[field]:
                missing.append(field)
                errors.append(f"Missing required field: {field}")
        
        return {
            "is_valid": len(missing) == 0,
            "missing_fields": missing,
            "validation_errors": errors
        }
        
    except Exception as e:
        # Return error in structured format
        return {
            "is_valid": False,
            "missing_fields": [],
            "validation_errors": [f"Validation failed: {str(e)}"]
        }
```

## Example Skills

See the `skills/` directory for complete examples:

1. **RiskCalculator** - Python function for financial risk scoring
2. **LoanTermsCalculator** - Python function for loan calculations
3. **InvoiceGenerator** - Python function for invoice generation
4. **DatabaseUserFetcher** - Direct PostgreSQL query
5. **CandidateDataEnricher** - Multi-source data pipeline
6. **ExternalAPIValidator** - Synchronous HTTP call
7. **DocumentParser** - External script execution

## Testing Actions

### Unit Testing

```python
# test_actions.py
from business_logic import calculate_risk_score

def test_risk_calculation():
    result = calculate_risk_score(
        credit_score=750,
        income=75000,
        debt=15000,
        employment_years=5
    )
    
    assert result['risk_score'] > 80
    assert result['risk_tier'] == 'low_risk'
    assert result['recommendation'] == 'approve'
```

### Integration Testing

```python
# test_action_executor.py
from engine import _execute_action_skill, Skill, ActionConfig, ActionType

async def test_action_execution():
    skill = Skill(
        name="TestSkill",
        executor="action",
        requires={"x", "y"},
        produces={"sum"},
        action=ActionConfig(
            type=ActionType.PYTHON_FUNCTION,
            module="test_actions",
            function="add"
        )
    )
    
    state = {"data_store": {"x": 5, "y": 3}, "thread_id": "test"}
    result = await _execute_action_skill(skill, state, {"x": 5, "y": 3})
    
    assert result['data_store']['sum'] == 8
```

## Performance Comparison

| Operation | LLM Executor | Action Executor | Speedup |
|-----------|-------------|-----------------|---------|
| Risk calculation | ~2-3s | ~10ms | 200-300x |
| Database query | ~3-5s | ~50ms | 60-100x |
| Invoice generation | ~2-4s | ~5ms | 400-800x |
| Document parsing | ~5-10s | ~500ms | 10-20x |

**Cost comparison (per 1000 executions):**
- LLM executor: ~$5-10 (depending on model)
- Action executor: < $0.01 (compute only)

## Migration Guide

### Converting LLM Skills to Actions

**Before (LLM):**
```yaml
name: RiskCalculator
executor: llm
prompt: "Calculate risk score based on credit_score={credit_score}, income={income}..."
```

**After (Action):**
```yaml
name: RiskCalculator
executor: action
action:
  type: python_function
  module: business_logic
  function: calculate_risk_score
```

**Benefits:**
- 200x faster
- 99.9% cheaper
- Deterministic results
- Unit testable
- No prompt engineering needed

## Troubleshooting

### Action Not Found
```
RuntimeError: Function 'calculate_risk' not found in registry
```

**Solutions:**
1. Check function is decorated with `@action`
2. Verify module is in `auto_discover_actions()` list
3. Check module/function names in skill YAML match exactly

### Signature Mismatch
```
RuntimeError: Function signature mismatch. Expected: ['x', 'y'], Provided: ['a', 'b']
```

**Solution:** Ensure skill's `requires` fields match function parameters exactly.

### Timeout Errors
```
RuntimeError: Script timed out after 30 seconds
```

**Solution:** Increase timeout in action config or optimize the operation.

## Roadmap

- [ ] Redis data source support
- [ ] Action result caching
- [ ] Async action batching
- [ ] Action performance metrics
- [ ] Visual action flow editor
- [ ] Action marketplace/registry

## See Also

- [Engine Documentation](./engine.py) - Core framework
- [Actions Module](./actions.py) - Decorator and utilities
- [Business Logic Examples](./business_logic/) - Sample actions
- [Skills Directory](./skills/) - Example skills
