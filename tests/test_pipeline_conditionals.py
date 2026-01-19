"""
Unit tests for data pipeline conditional execution logic.

Tests cover:
- Nested path access
- All 12 conditional operators
- Enhanced contains/not_contains with arrays
- Conditional step execution
- run_if/skip_if logic
"""

import sys
from pathlib import Path

# Add parent directory to path to import engine module
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from typing import Any, Dict
from engine import (
    _get_nested_value,
    _evaluate_condition,
    _check_step_condition,
)


class TestNestedPathAccess:
    """Test _get_nested_value function for dot-notation path access"""
    
    def test_simple_nested_access(self):
        data = {"user": {"name": "John"}}
        assert _get_nested_value(data, "user.name") == "John"
    
    def test_deep_nested_access(self):
        data = {"company": {"department": {"team": {"lead": "Alice"}}}}
        assert _get_nested_value(data, "company.department.team.lead") == "Alice"
    
    def test_array_index_access(self):
        data = {"orders": [{"id": 1}, {"id": 2}, {"id": 3}]}
        assert _get_nested_value(data, "orders.0.id") == 1
        assert _get_nested_value(data, "orders.2.id") == 3
    
    def test_mixed_nested_array_access(self):
        data = {
            "company": {
                "departments": [
                    {"name": "Engineering", "employees": [{"name": "Bob"}]}
                ]
            }
        }
        assert _get_nested_value(data, "company.departments.0.employees.0.name") == "Bob"
    
    def test_nonexistent_path_returns_none(self):
        data = {"user": {"name": "John"}}
        assert _get_nested_value(data, "user.email") is None
        assert _get_nested_value(data, "company.name") is None
    
    def test_array_index_out_of_bounds_returns_none(self):
        data = {"items": [1, 2, 3]}
        assert _get_nested_value(data, "items.10") is None
    
    def test_invalid_array_index_returns_none(self):
        data = {"items": [1, 2, 3]}
        assert _get_nested_value(data, "items.abc") is None
    
    def test_empty_path_returns_data(self):
        data = {"key": "value"}
        assert _get_nested_value(data, "") == data
    
    def test_accessing_none_returns_none(self):
        data = {"user": None}
        assert _get_nested_value(data, "user.name") is None


class TestEqualityOperators:
    """Test equals and not_equals operators"""
    
    def test_equals_string(self):
        assert _evaluate_condition("active", "equals", "active") is True
        assert _evaluate_condition("active", "equals", "inactive") is False
    
    def test_equals_number(self):
        assert _evaluate_condition(42, "equals", 42) is True
        assert _evaluate_condition(42, "equals", 100) is False
    
    def test_equals_boolean(self):
        assert _evaluate_condition(True, "equals", True) is True
        assert _evaluate_condition(True, "equals", False) is False
    
    def test_not_equals(self):
        assert _evaluate_condition("active", "not_equals", "deleted") is True
        assert _evaluate_condition("active", "not_equals", "active") is False


class TestContainsOperators:
    """Test contains and not_contains operators with single values and arrays (case-insensitive)"""
    
    def test_contains_single_value_in_string(self):
        assert _evaluate_condition("Operation successful", "contains", "success") is True
        assert _evaluate_condition("Operation failed", "contains", "success") is False
        # Case-insensitive
        assert _evaluate_condition("Operation SUCCESSFUL", "contains", "success") is True
        assert _evaluate_condition("OPERATION successful", "contains", "SUCCESS") is True
    
    def test_contains_single_value_in_array(self):
        assert _evaluate_condition(["admin", "user"], "contains", "admin") is True
        assert _evaluate_condition(["admin", "user"], "contains", "owner") is False
        # Case-insensitive
        assert _evaluate_condition(["Admin", "User"], "contains", "admin") is True
        assert _evaluate_condition(["ADMIN", "USER"], "contains", "admin") is True
    
    def test_contains_array_values_in_string(self):
        # ANY of the values should match (case-insensitive)
        assert _evaluate_condition("Currently processing", "contains", ["pending", "processing"]) is True
        assert _evaluate_condition("Completed successfully", "contains", ["error", "failed"]) is False
        # Case-insensitive
        assert _evaluate_condition("Currently PROCESSING", "contains", ["pending", "processing"]) is True
        assert _evaluate_condition("COMPLETED successfully", "contains", ["ERROR", "failed"]) is False
    
    def test_contains_array_values_in_array(self):
        # ANY of the expected values should be in actual (case-insensitive)
        assert _evaluate_condition(["read", "admin"], "contains", ["admin", "owner"]) is True
        assert _evaluate_condition(["read", "write"], "contains", ["admin", "owner"]) is False
        # Case-insensitive
        assert _evaluate_condition(["READ", "Admin"], "contains", ["admin", "owner"]) is True
        assert _evaluate_condition(["Read", "WRITE"], "contains", ["ADMIN", "owner"]) is False
    
    def test_not_contains_single_value_in_string(self):
        assert _evaluate_condition("Success", "not_contains", "error") is True
        assert _evaluate_condition("An error occurred", "not_contains", "error") is False
        # Case-insensitive
        assert _evaluate_condition("Success", "not_contains", "ERROR") is True
        assert _evaluate_condition("Error occurred", "not_contains", "error") is False
        assert _evaluate_condition("An ERROR occurred", "not_contains", "error") is False
    
    def test_not_contains_single_value_in_array(self):
        assert _evaluate_condition(["user", "guest"], "not_contains", "admin") is True
        assert _evaluate_condition(["admin", "user"], "not_contains", "admin") is False
        # Case-insensitive
        assert _evaluate_condition(["User", "Guest"], "not_contains", "ADMIN") is True
        assert _evaluate_condition(["Admin", "user"], "not_contains", "admin") is False
    
    def test_not_contains_array_values_in_string(self):
        # NONE of the values should match (case-insensitive)
        assert _evaluate_condition("Success", "not_contains", ["error", "failed"]) is True
        assert _evaluate_condition("error occurred", "not_contains", ["error", "failed"]) is False
        # Case-insensitive
        assert _evaluate_condition("Success", "not_contains", ["ERROR", "FAILED"]) is True
        assert _evaluate_condition("Error occurred", "not_contains", ["error", "failed"]) is False
        assert _evaluate_condition("FAILED operation", "not_contains", ["error", "failed"]) is False
    
    def test_not_contains_array_values_in_array(self):
        # NONE of the expected values should be in actual (case-insensitive)
        assert _evaluate_condition(["read", "write"], "not_contains", ["admin", "owner"]) is True
        assert _evaluate_condition(["read", "admin"], "not_contains", ["admin", "owner"]) is False
        # Case-insensitive
        assert _evaluate_condition(["READ", "Write"], "not_contains", ["ADMIN", "owner"]) is True
        assert _evaluate_condition(["read", "Admin"], "not_contains", ["admin", "OWNER"]) is False


class TestArrayMembershipOperators:
    """Test in and not_in operators"""
    
    def test_in_operator(self):
        assert _evaluate_condition("admin", "in", ["admin", "owner", "user"]) is True
        assert _evaluate_condition("guest", "in", ["admin", "owner", "user"]) is False
    
    def test_in_operator_with_non_array_returns_false(self):
        assert _evaluate_condition("admin", "in", "not_an_array") is False
    
    def test_not_in_operator(self):
        assert _evaluate_condition("guest", "not_in", ["deleted", "banned"]) is True
        assert _evaluate_condition("deleted", "not_in", ["deleted", "banned"]) is False
    
    def test_not_in_operator_with_non_array_returns_true(self):
        assert _evaluate_condition("admin", "not_in", "not_an_array") is True


class TestNumericComparisonOperators:
    """Test gt, gte, lt, lte operators"""
    
    def test_greater_than(self):
        assert _evaluate_condition(100, "gt", 50) is True
        assert _evaluate_condition(50, "gt", 100) is False
        assert _evaluate_condition(50, "gt", 50) is False
    
    def test_greater_than_or_equal(self):
        assert _evaluate_condition(100, "gte", 50) is True
        assert _evaluate_condition(50, "gte", 50) is True
        assert _evaluate_condition(25, "gte", 50) is False
    
    def test_less_than(self):
        assert _evaluate_condition(50, "lt", 100) is True
        assert _evaluate_condition(100, "lt", 50) is False
        assert _evaluate_condition(50, "lt", 50) is False
    
    def test_less_than_or_equal(self):
        assert _evaluate_condition(50, "lte", 100) is True
        assert _evaluate_condition(50, "lte", 50) is True
        assert _evaluate_condition(100, "lte", 50) is False
    
    def test_numeric_comparison_with_strings(self):
        # Should convert strings to numbers
        assert _evaluate_condition("100", "gt", "50") is True
        assert _evaluate_condition("50.5", "lt", "100.8") is True


class TestEmptinessOperators:
    """Test is_empty and is_not_empty operators"""
    
    def test_is_empty_with_none(self):
        assert _evaluate_condition(None, "is_empty", None) is True
    
    def test_is_empty_with_empty_string(self):
        assert _evaluate_condition("", "is_empty", None) is True
    
    def test_is_empty_with_empty_array(self):
        assert _evaluate_condition([], "is_empty", None) is True
    
    def test_is_empty_with_empty_dict(self):
        assert _evaluate_condition({}, "is_empty", None) is True
    
    def test_is_empty_with_zero(self):
        assert _evaluate_condition(0, "is_empty", None) is True
    
    def test_is_empty_with_false(self):
        assert _evaluate_condition(False, "is_empty", None) is True
    
    def test_is_empty_with_non_empty_values(self):
        assert _evaluate_condition("text", "is_empty", None) is False
        assert _evaluate_condition([1, 2], "is_empty", None) is False
        assert _evaluate_condition({"key": "value"}, "is_empty", None) is False
        assert _evaluate_condition(1, "is_empty", None) is False
    
    def test_is_not_empty_with_none(self):
        assert _evaluate_condition(None, "is_not_empty", None) is False
    
    def test_is_not_empty_with_empty_values(self):
        assert _evaluate_condition("", "is_not_empty", None) is False
        assert _evaluate_condition([], "is_not_empty", None) is False
        assert _evaluate_condition({}, "is_not_empty", None) is False
    
    def test_is_not_empty_with_non_empty_values(self):
        assert _evaluate_condition("text", "is_not_empty", None) is True
        assert _evaluate_condition([1], "is_not_empty", None) is True
        assert _evaluate_condition({"key": "value"}, "is_not_empty", None) is True
        assert _evaluate_condition(1, "is_not_empty", None) is True
        assert _evaluate_condition(True, "is_not_empty", None) is True


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_unknown_operator_returns_false(self):
        assert _evaluate_condition("value", "unknown_op", "test") is False
    
    def test_numeric_comparison_on_invalid_types_returns_false(self):
        # Should catch exception and return False
        assert _evaluate_condition("not_a_number", "gt", "also_not_a_number") is False
    
    def test_condition_evaluation_handles_exceptions_gracefully(self):
        # Various edge cases that might raise exceptions
        assert _evaluate_condition(None, "contains", "test") is False
        assert _evaluate_condition([], "gt", 10) is False


class TestStepConditionChecking:
    """Test _check_step_condition for run_if and skip_if"""
    
    def test_no_condition_always_runs(self):
        step = {"type": "query", "name": "test_step"}
        context = {"data": "value"}
        assert _check_step_condition(step, context) is True
    
    def test_run_if_condition_true(self):
        step = {
            "type": "query",
            "run_if": {
                "field": "user.plan",
                "operator": "equals",
                "value": "premium"
            }
        }
        context = {"user": {"plan": "premium"}}
        assert _check_step_condition(step, context) is True
    
    def test_run_if_condition_false(self):
        step = {
            "type": "query",
            "run_if": {
                "field": "user.plan",
                "operator": "equals",
                "value": "premium"
            }
        }
        context = {"user": {"plan": "free"}}
        assert _check_step_condition(step, context) is False
    
    def test_skip_if_condition_true(self):
        step = {
            "type": "query",
            "skip_if": {
                "field": "data",
                "operator": "is_empty"
            }
        }
        context = {"data": []}
        assert _check_step_condition(step, context) is False  # Should be skipped
    
    def test_skip_if_condition_false(self):
        step = {
            "type": "query",
            "skip_if": {
                "field": "data",
                "operator": "is_empty"
            }
        }
        context = {"data": [1, 2, 3]}
        assert _check_step_condition(step, context) is True  # Should run
    
    def test_malformed_run_if_defaults_to_run(self):
        # Missing operator
        step = {
            "type": "query",
            "run_if": {
                "field": "user.plan"
            }
        }
        context = {"user": {"plan": "premium"}}
        assert _check_step_condition(step, context) is True
    
    def test_malformed_skip_if_defaults_to_run(self):
        # Missing field
        step = {
            "type": "query",
            "skip_if": {
                "operator": "equals"
            }
        }
        context = {"data": "value"}
        assert _check_step_condition(step, context) is True


class TestComplexScenarios:
    """Test complex real-world scenarios"""
    
    def test_check_premium_user_with_nested_data(self):
        context = {
            "order": {
                "id": 123,
                "total": 1500,
                "customer": {
                    "email": "user@example.com",
                    "plan": "premium"
                }
            }
        }
        
        # Check if order total > 1000
        assert _evaluate_condition(
            _get_nested_value(context, "order.total"),
            "gt",
            1000
        ) is True
        
        # Check if customer has email
        assert _evaluate_condition(
            _get_nested_value(context, "order.customer.email"),
            "is_not_empty",
            None
        ) is True
        
        # Check if customer is premium
        assert _evaluate_condition(
            _get_nested_value(context, "order.customer.plan"),
            "equals",
            "premium"
        ) is True
    
    def test_error_detection_in_logs_with_array_contains(self):
        context = {
            "logs": {
                "message": "Critical error occurred during processing",
                "level": "error"
            }
        }
        
        # Check if message contains any error keywords
        assert _evaluate_condition(
            _get_nested_value(context, "logs.message"),
            "contains",
            ["error", "exception", "failed", "critical"]
        ) is True
    
    def test_user_permission_validation(self):
        context = {
            "user": {
                "role": "admin",
                "permissions": ["read", "write", "admin"],
                "status": "active"
            }
        }
        
        # Check if user is admin or owner
        assert _evaluate_condition(
            _get_nested_value(context, "user.role"),
            "in",
            ["admin", "owner"]
        ) is True
        
        # Check if user has admin permission
        assert _evaluate_condition(
            _get_nested_value(context, "user.permissions"),
            "contains",
            "admin"
        ) is True
        
        # Check if status is not deleted or banned
        assert _evaluate_condition(
            _get_nested_value(context, "user.status"),
            "not_in",
            ["deleted", "banned"]
        ) is True
    
    def test_array_indexing_in_complex_structure(self):
        context = {
            "companies": [
                {
                    "name": "Acme Corp",
                    "departments": [
                        {
                            "name": "Engineering",
                            "employees": [
                                {"name": "Alice", "role": "Lead"},
                                {"name": "Bob", "role": "Dev"}
                            ]
                        }
                    ]
                }
            ]
        }
        
        # Access deeply nested employee role
        role = _get_nested_value(context, "companies.0.departments.0.employees.0.role")
        assert role == "Lead"
        
        # Check if role equals Lead
        assert _evaluate_condition(role, "equals", "Lead") is True


class TestIntegrationScenarios:
    """Test complete pipeline step scenarios"""
    
    def test_conditional_step_with_run_if(self):
        step = {
            "type": "query",
            "name": "premium_query",
            "run_if": {
                "field": "user.plan",
                "operator": "in",
                "value": ["premium", "enterprise"]
            }
        }
        
        # Premium user - should run
        context_premium = {"user": {"plan": "premium"}}
        assert _check_step_condition(step, context_premium) is True
        
        # Free user - should skip
        context_free = {"user": {"plan": "free"}}
        assert _check_step_condition(step, context_free) is False
    
    def test_conditional_step_with_skip_if(self):
        step = {
            "type": "transform",
            "name": "process_data",
            "skip_if": {
                "field": "results",
                "operator": "is_empty"
            }
        }
        
        # Empty results - should skip
        context_empty = {"results": []}
        assert _check_step_condition(step, context_empty) is False
        
        # Has results - should run
        context_with_data = {"results": [{"id": 1}]}
        assert _check_step_condition(step, context_with_data) is True
    
    def test_multiple_conditions_scenario(self):
        # Scenario: Process order only if:
        # 1. Order total > 100
        # 2. Customer email is not empty
        # 3. Status is not cancelled
        
        context = {
            "order": {
                "total": 150,
                "status": "pending",
                "customer": {"email": "test@example.com"}
            }
        }
        
        # Check all conditions
        total_check = _evaluate_condition(
            _get_nested_value(context, "order.total"),
            "gt",
            100
        )
        
        email_check = _evaluate_condition(
            _get_nested_value(context, "order.customer.email"),
            "is_not_empty",
            None
        )
        
        status_check = _evaluate_condition(
            _get_nested_value(context, "order.status"),
            "not_equals",
            "cancelled"
        )
        
        # All should pass
        assert total_check is True
        assert email_check is True
        assert status_check is True


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
