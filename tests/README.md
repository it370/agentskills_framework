# Test Suite for AgentSkills Framework

## Data Pipeline Conditional Execution Tests

Comprehensive test suite covering all conditional logic features for data pipelines.

### Test Coverage (57 tests)

- **Nested Path Access** (9 tests): Dot-notation path traversal, array indexing
- **Equality Operators** (4 tests): `equals`, `not_equals`
- **Contains Operators** (8 tests): `contains`, `not_contains` with single values and arrays
- **Array Membership** (4 tests): `in`, `not_in`
- **Numeric Comparison** (5 tests): `gt`, `gte`, `lt`, `lte`
- **Emptiness Checks** (11 tests): `is_empty`, `is_not_empty`
- **Error Handling** (3 tests): Unknown operators, invalid types, exceptions
- **Step Condition Checking** (7 tests): `run_if`, `skip_if`, malformed conditions
- **Complex Scenarios** (4 tests): Real-world nested data validation
- **Integration Scenarios** (3 tests): Complete pipeline workflows

### Running Tests

#### Prerequisites
Ensure you're in the `clearstar` conda environment:
```powershell
conda activate clearstar
```

#### Run All Tests
```powershell
# Basic run
python tests/test_pipeline_conditionals.py

# With verbose output
python tests/test_pipeline_conditionals.py -v

# With pytest (recommended)
pytest tests/test_pipeline_conditionals.py -v

# Run specific test class
pytest tests/test_pipeline_conditionals.py::TestContainsOperators -v

# Run with coverage
pytest tests/test_pipeline_conditionals.py --cov=engine --cov-report=html
```

#### From Project Root
```powershell
# Activate environment and run
conda activate clearstar; python tests/test_pipeline_conditionals.py
```

### Test File Structure

```
tests/
├── __init__.py                      # Makes tests a Python package
├── test_pipeline_conditionals.py    # Main test suite (501 lines)
└── README.md                        # This file
```

### Key Features Tested

#### 1. Enhanced Contains with Arrays
```python
# Single value
_evaluate_condition("Currently processing", "contains", "processing")  # True

# Multiple values (ANY match)
_evaluate_condition("Currently processing", "contains", ["pending", "processing"])  # True
```

#### 2. Nested Path Access
```python
# Deep nesting with arrays
_get_nested_value(data, "companies.0.departments.0.employees.0.role")  # "Lead"
```

#### 3. Step Conditions
```python
# run_if: Execute only if condition is true
step = {
    "run_if": {
        "field": "user.plan",
        "operator": "equals",
        "value": "premium"
    }
}

# skip_if: Skip if condition is true
step = {
    "skip_if": {
        "field": "data",
        "operator": "is_empty"
    }
}
```

### Important Notes

#### Case Sensitivity
Most operators are **case-sensitive**, except `contains` and `not_contains`:
```python
# equals is case-sensitive
_evaluate_condition("Active", "equals", "active")  # False

# contains and not_contains are case-insensitive
_evaluate_condition("Error", "contains", "error")  # True (case-insensitive)
_evaluate_condition("ERROR", "contains", "error")  # True (case-insensitive)
_evaluate_condition("Success", "not_contains", "ERROR")  # True (case-insensitive)
```

#### Operator Behavior
- **contains/not_contains**: Works with strings and arrays, **case-insensitive**
- **in/not_in**: Value must be in the expected array, case-sensitive
- **Numeric comparisons**: Auto-converts strings to numbers
- **Emptiness**: `None`, `""`, `[]`, `{}`, `0`, `False` are all "empty"

### Adding New Tests

1. Choose the appropriate test class based on functionality
2. Follow the naming convention: `test_<feature_description>`
3. Add clear assertions with comments explaining expected behavior
4. Include edge cases and error scenarios

Example:
```python
class TestNewFeature:
    """Test description"""
    
    def test_basic_functionality(self):
        # Test basic case
        assert _evaluate_condition(...) is True
    
    def test_edge_case(self):
        # Test edge case behavior
        assert _evaluate_condition(...) is False
```

### Continuous Integration

These tests should be run:
- Before committing conditional logic changes
- As part of CI/CD pipeline
- When updating operator implementations
- When adding new pipeline features

### Test Results

All tests currently passing:
```
======================= 57 passed, 3 warnings in 0.28s ========================
```

### Troubleshooting

#### ModuleNotFoundError: No module named 'engine'
**Solution**: The test file automatically adds the parent directory to the Python path. Ensure you're running from the project root.

#### Tests fail with import errors
**Solution**: Activate the `clearstar` conda environment:
```powershell
conda activate clearstar
```

#### Specific test failures
**Solution**: Run with verbose mode to see detailed error messages:
```powershell
pytest tests/test_pipeline_conditionals.py -v --tb=short
```

### Documentation

For detailed information about conditional execution features, see:
- `documentations/DATA_PIPELINE_CONDITIONAL_EXECUTION.md`

For implementation details, see:
- `engine.py` (search for `_evaluate_condition`, `_get_nested_value`, `_check_step_condition`)

---

**Last Updated**: January 2026
**Test Suite Version**: 1.0
**Coverage**: 100% of conditional operators
