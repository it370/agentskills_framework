"""
Unit tests for pipeline string interpolation with nested object access.

Tests the _format_with_ctx function which is used to interpolate
placeholders in query strings, URLs, and other pipeline step parameters.
"""

import sys
from pathlib import Path

# Add parent directory to path to import engine module
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from engine import _format_with_ctx


class TestSimpleInterpolation:
    """Test basic placeholder replacement"""
    
    def test_simple_string_placeholder(self):
        result = _format_with_ctx("User: {user_id}", {"user_id": "123"})
        assert result == "User: 123"
    
    def test_simple_number_placeholder(self):
        result = _format_with_ctx("ID: {id}", {"id": 42})
        assert result == "ID: 42"
    
    def test_multiple_placeholders(self):
        ctx = {"name": "Alice", "age": 30}
        result = _format_with_ctx("Name: {name}, Age: {age}", ctx)
        assert result == "Name: Alice, Age: 30"
    
    def test_no_placeholders(self):
        result = _format_with_ctx("SELECT * FROM users", {})
        assert result == "SELECT * FROM users"
    
    def test_same_placeholder_multiple_times(self):
        result = _format_with_ctx("{id} - {id} - {id}", {"id": 5})
        assert result == "5 - 5 - 5"


class TestNestedObjectAccess:
    """Test nested object path interpolation"""
    
    def test_simple_nested_path(self):
        ctx = {"user": {"name": "Bob"}}
        result = _format_with_ctx("Name: {user.name}", ctx)
        assert result == "Name: Bob"
    
    def test_deep_nested_path(self):
        ctx = {"company": {"department": {"team": {"lead": "Alice"}}}}
        result = _format_with_ctx("Lead: {company.department.team.lead}", ctx)
        assert result == "Lead: Alice"
    
    def test_nested_number(self):
        ctx = {"order": {"total": 150}}
        result = _format_with_ctx("Total: {order.total}", ctx)
        assert result == "Total: 150"
    
    def test_mixed_simple_and_nested(self):
        ctx = {"user_id": 1, "user": {"email": "test@example.com"}}
        result = _format_with_ctx("ID: {user_id}, Email: {user.email}", ctx)
        assert result == "ID: 1, Email: test@example.com"


class TestArrayIndexing:
    """Test array indexing in paths"""
    
    def test_array_index_simple(self):
        ctx = {"items": [{"name": "Item1"}, {"name": "Item2"}]}
        result = _format_with_ctx("First: {items.0.name}", ctx)
        assert result == "First: Item1"
    
    def test_array_index_second_item(self):
        ctx = {"orders": [{"id": 10}, {"id": 20}, {"id": 30}]}
        result = _format_with_ctx("Order: {orders.2.id}", ctx)
        assert result == "Order: 30"
    
    def test_nested_array_access(self):
        ctx = {
            "company": {
                "departments": [
                    {"name": "Eng", "employees": [{"name": "Alice"}]}
                ]
            }
        }
        result = _format_with_ctx("Name: {company.departments.0.employees.0.name}", ctx)
        assert result == "Name: Alice"


class TestSQLQueryExamples:
    """Test real-world SQL query scenarios"""
    
    def test_simple_where_clause(self):
        ctx = {"customer_id": 123}
        query = _format_with_ctx("SELECT * FROM orders WHERE customer_id = {customer_id}", ctx)
        assert query == "SELECT * FROM orders WHERE customer_id = 123"
    
    def test_nested_customer_id(self):
        ctx = {"order": {"customer_id": 456}}
        query = _format_with_ctx("SELECT * FROM customers WHERE id = {order.customer_id}", ctx)
        assert query == "SELECT * FROM customers WHERE id = 456"
    
    def test_insert_with_nested_values(self):
        ctx = {"user": {"id": 1, "email": "user@example.com"}, "status": "active"}
        query = _format_with_ctx(
            "INSERT INTO logs (user_id, email, status) VALUES ({user.id}, '{user.email}', '{status}')",
            ctx
        )
        assert query == "INSERT INTO logs (user_id, email, status) VALUES (1, 'user@example.com', 'active')"
    
    def test_complex_join_query(self):
        ctx = {
            "filters": {"start_date": "2024-01-01", "category": "electronics"},
            "user": {"id": 99}
        }
        query = _format_with_ctx(
            "SELECT * FROM orders WHERE user_id = {user.id} AND category = '{filters.category}' AND date >= '{filters.start_date}'",
            ctx
        )
        assert query == "SELECT * FROM orders WHERE user_id = 99 AND category = 'electronics' AND date >= '2024-01-01'"


class TestAPIURLExamples:
    """Test URL construction with nested values"""
    
    def test_rest_url_with_nested_id(self):
        ctx = {"order": {"id": 123}}
        url = _format_with_ctx("https://api.example.com/orders/{order.id}", ctx)
        assert url == "https://api.example.com/orders/123"
    
    def test_url_with_query_params(self):
        ctx = {"user": {"id": 5, "role": "admin"}}
        url = _format_with_ctx("https://api.example.com/users?id={user.id}&role={user.role}", ctx)
        assert url == "https://api.example.com/users?id=5&role=admin"


class TestNoneValues:
    """Test handling of None values"""
    
    def test_none_value_simple(self):
        ctx = {"value": None}
        result = _format_with_ctx("Value: {value}", ctx)
        assert result == "Value: "
    
    def test_none_value_nested(self):
        ctx = {"user": {"email": None}}
        result = _format_with_ctx("Email: {user.email}", ctx)
        assert result == "Email: "


class TestErrorHandling:
    """Test error handling for missing placeholders"""
    
    def test_missing_simple_key(self):
        with pytest.raises(RuntimeError) as exc_info:
            _format_with_ctx("User: {user_id}", {})
        assert "Missing placeholder 'user_id'" in str(exc_info.value)
        assert "Available keys:" in str(exc_info.value)
    
    def test_missing_nested_first_key(self):
        ctx = {"other": "value"}
        with pytest.raises(RuntimeError) as exc_info:
            _format_with_ctx("Name: {user.name}", ctx)
        assert "Missing placeholder 'user.name'" in str(exc_info.value)
        assert "First key 'user' not found" in str(exc_info.value)
    
    def test_missing_nested_second_key(self):
        # When first key exists but nested path doesn't, we get None (empty string)
        ctx = {"user": {"id": 1}}
        result = _format_with_ctx("Email: {user.email}", ctx)
        assert result == "Email: "
    
    def test_error_shows_available_keys(self):
        ctx = {"foo": 1, "bar": 2}
        with pytest.raises(RuntimeError) as exc_info:
            _format_with_ctx("{missing}", ctx)
        error_msg = str(exc_info.value)
        assert "bar" in error_msg
        assert "foo" in error_msg


class TestEdgeCases:
    """Test edge cases and special scenarios"""
    
    def test_empty_string_value(self):
        ctx = {"name": ""}
        result = _format_with_ctx("Name: {name}", ctx)
        assert result == "Name: "
    
    def test_boolean_values(self):
        ctx = {"active": True, "deleted": False}
        result = _format_with_ctx("Active: {active}, Deleted: {deleted}", ctx)
        assert result == "Active: True, Deleted: False"
    
    def test_zero_value(self):
        ctx = {"count": 0}
        result = _format_with_ctx("Count: {count}", ctx)
        assert result == "Count: 0"
    
    def test_special_characters_in_value(self):
        ctx = {"message": "Hello 'world' & <friends>"}
        result = _format_with_ctx("Message: {message}", ctx)
        assert result == "Message: Hello 'world' & <friends>"
    
    def test_nested_with_underscore_keys(self):
        ctx = {"user_profile": {"first_name": "John"}}
        result = _format_with_ctx("Name: {user_profile.first_name}", ctx)
        assert result == "Name: John"
    
    def test_array_out_of_bounds(self):
        ctx = {"items": [1, 2, 3]}
        result = _format_with_ctx("Item: {items.10}", ctx)
        assert result == "Item: "  # Returns empty string for out of bounds


class TestBackwardCompatibility:
    """Ensure old simple placeholder syntax still works"""
    
    def test_old_format_still_works(self):
        # Old code that just used {simple_key} should continue working
        ctx = {"id": 123, "name": "Test", "value": 99.9}
        
        result1 = _format_with_ctx("SELECT * FROM table WHERE id = {id}", ctx)
        assert result1 == "SELECT * FROM table WHERE id = 123"
        
        result2 = _format_with_ctx("Name: {name}, Value: {value}", ctx)
        assert result2 == "Name: Test, Value: 99.9"


class TestComplexRealWorldScenarios:
    """Test complex real-world pipeline scenarios"""
    
    def test_multi_step_pipeline_context(self):
        # Simulates context after multiple pipeline steps
        ctx = {
            "order_id": 123,
            "order": {"customer_id": 456, "total": 999.99},
            "customer": {"email": "customer@example.com", "name": "John Doe"},
            "items": [{"id": 1, "name": "Widget"}, {"id": 2, "name": "Gadget"}]
        }
        
        # Query 1: Using simple key
        q1 = _format_with_ctx("SELECT * FROM orders WHERE id = {order_id}", ctx)
        assert q1 == "SELECT * FROM orders WHERE id = 123"
        
        # Query 2: Using nested customer_id from order
        q2 = _format_with_ctx("SELECT * FROM customers WHERE id = {order.customer_id}", ctx)
        assert q2 == "SELECT * FROM customers WHERE id = 456"
        
        # Query 3: Using nested customer data
        q3 = _format_with_ctx("INSERT INTO notifications (email, name) VALUES ('{customer.email}', '{customer.name}')", ctx)
        assert q3 == "INSERT INTO notifications (email, name) VALUES ('customer@example.com', 'John Doe')"
        
        # Query 4: Using array indexing
        q4 = _format_with_ctx("SELECT * FROM products WHERE id = {items.0.id}", ctx)
        assert q4 == "SELECT * FROM products WHERE id = 1"
        
        # Query 5: Mixing everything
        q5 = _format_with_ctx(
            "UPDATE orders SET customer_name = '{customer.name}', first_item = '{items.0.name}' WHERE id = {order_id}",
            ctx
        )
        assert q5 == "UPDATE orders SET customer_name = 'John Doe', first_item = 'Widget' WHERE id = 123"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
