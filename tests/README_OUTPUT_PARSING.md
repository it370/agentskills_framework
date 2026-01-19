# Output Parsing Test Suite

Comprehensive test suite for skill output parsing across all executor types.

## Overview

This test suite validates output mapping, `produces` validation, `optional_produces` handling, and edge cases for all executor types in the AgentSkills framework.

## Test Coverage

### Executor Types Tested

1. **REST Executor** (6 tests)
2. **ACTION Executor - DATA_QUERY** (5 tests)
3. **ACTION Executor - DATA_PIPELINE** (8 tests)
4. **ACTION Executor - PYTHON_FUNCTION** (2 tests)
5. **ACTION Executor - SCRIPT** (2 tests)
6. **ACTION Executor - HTTP_CALL** (2 tests)
7. **LLM Executor** (3 tests)
8. **Edge Cases** (3 tests)

**Total: 31 tests**

## Running Tests

### Run all tests:
```bash
python tests/test_output_parsing.py
```

### Run with pytest:
```bash
python -m pytest tests/test_output_parsing.py -v
```

### Run specific test:
```bash
python -m pytest tests/test_output_parsing.py::TestOutputParsing::test_data_pipeline_single_produces_with_optional -v
```

## Key Concepts Tested

### 1. Single vs Multiple Produces Behavior

**Single Produces (Non-Pipeline):**
- Wraps the ENTIRE result dict under the single produces key
- Example: `produces={"output"}` with result `{"data": [1,2,3]}` → `{"output": {"data": [1,2,3]}}`

**Multiple Produces:**
- Key-based extraction (no wrapping)
- Example: `produces={"data", "count"}` with result `{"data": [], "count": 5}` → `{"data": [], "count": 5}`

**Data Pipeline (Special Case):**
- Single produces extracts specific key from pipeline output
- Example: `produces={"game_name"}` with result `{"game_name": "chess", "extra": "ignored"}` → `{"game_name": "chess"}`

### 2. Optional Produces

- Keys in `optional_produces` are extracted if present
- Missing optional keys do NOT cause errors
- Optional keys never overwrite required `produces` keys
- Works with all executor types

### 3. Strict Validation

- Required `produces` keys MUST exist or skill execution fails
- Missing required keys throw `ValueError`
- Enforced for all executor types except where explicitly handled

## Test Categories

### REST Executor Tests

```python
test_rest_single_produces              # Basic single key extraction
test_rest_multiple_produces            # Multiple key extraction
test_rest_with_optional_produces       # Optional keys present
test_rest_optional_produces_missing    # Optional keys missing (no error)
test_rest_extra_keys_ignored           # Extra keys not extracted
test_rest_no_data_store                # Missing data_store returns empty
```

### DATA_QUERY Tests

```python
test_data_query_single_produces                    # Single produces wraps result
test_data_query_multiple_produces                  # Multiple produces key mapping
test_data_query_with_optional_produces             # Optional keys extracted
test_data_query_optional_missing                   # Optional missing (no error)
test_data_query_missing_required_produces_error    # Required key missing errors
```

### DATA_PIPELINE Tests (Special Cases)

```python
test_data_pipeline_single_produces_match           # Single produces extracts specific key
test_data_pipeline_single_produces_with_optional   # With optional produces
test_data_pipeline_single_produces_mismatch_error  # Required key missing errors
test_data_pipeline_multiple_step_outputs           # Multiple pipeline steps
test_data_pipeline_array_outputs                   # Array/list outputs
test_data_pipeline_none_values                     # None values handled
test_data_pipeline_empty_result                    # Empty result errors
test_data_pipeline_complex_nested_data             # Complex nested structures
```

### Other Action Types

```python
test_python_function_with_optional                    # Single produces wrapping
test_python_function_multiple_produces_with_optional  # Multiple + optional
test_script_with_optional_missing                     # Single produces wrapping
test_script_multiple_produces_optional_missing        # Multiple + optional missing
test_http_call_with_multiple_optional                 # Single produces wrapping
test_http_call_multiple_produces_with_optional        # Multiple + optional
```

### LLM Executor Tests

```python
test_llm_single_produces           # Single output extraction
test_llm_with_optional_produces    # With optional outputs
test_llm_optional_produces_none    # Optional returning None (not included)
```

### Edge Cases

```python
test_non_dict_result_error               # Non-dict result throws error
test_empty_produces_copies_all           # Empty produces copies all keys
test_optional_does_not_overwrite_required # Optional never overwrites required
```

## Output Mapping Logic

### REST Executor
```python
# Extract from result["data_store"]
for key in produces:
    outputs[key] = data_store[key]
for key in optional_produces:
    if key in data_store:
        outputs[key] = data_store[key]
```

### ACTION Executor (Single Produces, Non-Pipeline)
```python
# Wrap entire result under single key
mapped_result[produces[0]] = entire_result_dict
```

### ACTION Executor (Multiple Produces)
```python
# Key-based extraction
for key in produces:
    mapped_result[key] = result[key]  # Error if missing
for key in optional_produces:
    if key in result:
        mapped_result[key] = result[key]  # No error if missing
```

### ACTION Executor (DATA_PIPELINE, Single Produces)
```python
# Extract specific key from pipeline output
if produces[0] in result:
    mapped_result[produces[0]] = result[produces[0]]
for key in optional_produces:
    if key in result:
        mapped_result[key] = result[key]
```

### LLM Executor
```python
# Extract from Pydantic model attributes
for key in produces:
    outputs[key] = getattr(result, key)  # Required
for key in optional_produces:
    val = getattr(result, key, None)
    if val is not None:
        outputs[key] = val  # Optional
```

## Examples

### Example 1: Data Pipeline with Optional Output

```python
skill = Skill(
    name="GamePicker",
    produces={"game_name"},
    optional_produces={"player_stats"},
    executor="action",
    action=ActionConfig(
        type=ActionType.DATA_PIPELINE,
        steps=[...]
    )
)

# Pipeline returns:
{
    "game_name": "chess",
    "player_stats": {"wins": 10},
    "internal_data": "ignored"
}

# Mapped result:
{
    "game_name": "chess",
    "player_stats": {"wins": 10}
}
# internal_data not in produces or optional_produces, so ignored
```

### Example 2: REST Executor with Missing Optional

```python
skill = Skill(
    name="FetchUser",
    produces={"user"},
    optional_produces={"metadata", "avatar_url"},
    executor="rest",
)

# REST returns in data_store:
{
    "user": {"id": 123, "name": "John"},
    "metadata": {"created": "2026-01-01"}
    # avatar_url missing
}

# Mapped result:
{
    "user": {"id": 123, "name": "John"},
    "metadata": {"created": "2026-01-01"}
}
# No error for missing avatar_url
```

### Example 3: Single Produces Wrapping (Non-Pipeline)

```python
skill = Skill(
    name="QueryDB",
    produces={"result"},
    executor="action",
    action=ActionConfig(type=ActionType.DATA_QUERY, query="SELECT *")
)

# Query returns:
{
    "users": [...],
    "count": 10
}

# Mapped result (entire dict wrapped):
{
    "result": {
        "users": [...],
        "count": 10
    }
}
```

## Common Patterns

### Pattern 1: Required + Optional Outputs
```python
produces={"required_data"}
optional_produces={"debug_info", "timing"}
```
- `required_data` MUST be present
- `debug_info` and `timing` extracted if present, no error if missing

### Pattern 2: Multiple Outputs, Some Optional
```python
produces={"users", "total_count"}
optional_produces={"page_info", "filters_applied"}
```
- Both `users` and `total_count` required
- Page info and filters optional

### Pattern 3: Pipeline with Conditional Outputs
```python
produces={"result"}
optional_produces={"error_details", "fallback_used"}
```
- Main result always required
- Optional fields only present in certain conditions

## Error Handling

### Errors That Stop Execution

1. **Missing Required Produces:**
   ```
   ValueError: Critical Error: Missing expected keys: {'required_key'}
   ```

2. **Non-Dict Result:**
   ```
   ValueError: Action TestSkill must return a dict, got <class 'list'>
   ```

3. **Pipeline Single Produces Mismatch:**
   ```
   ValueError: Critical Error: Missing expected key: expected_key
   ```

### Silent Handling (No Error)

1. Missing `optional_produces` keys
2. Extra keys in result not in `produces` or `optional_produces`
3. `None` values in `optional_produces` (LLM executor)

## Best Practices

1. **Use Multiple Produces for Structured Data:**
   ```python
   produces={"users", "count", "next_page"}  # Key-based extraction
   ```

2. **Use Single Produces for Wrapping:**
   ```python
   produces={"api_response"}  # Wraps entire result
   ```

3. **Use DATA_PIPELINE for Selective Extraction:**
   ```python
   # Pipeline outputs many intermediate keys, only extract needed ones
   produces={"final_result"}
   optional_produces={"intermediate_data"}
   ```

4. **Use optional_produces for Conditional Data:**
   ```python
   produces={"data"}
   optional_produces={"error", "warnings", "metadata"}
   ```

## Maintenance

When modifying output parsing logic:

1. Run this test suite to ensure no regressions
2. Add new tests for new executor types or edge cases
3. Update this README with new patterns

## Dependencies

- `unittest.mock` for mocking executors
- `asyncio` for async test execution
- `pytest` (optional, for better test reporting)

## License

Part of the AgentSkills Framework.
