# Data Pipeline Conditional Execution

## Overview

Data pipelines now support **conditional logic** for branching and dynamic execution flow. This allows you to build complex, deterministic workflows without LLM involvement.

---

## Features

### 1. Conditional Step Type (if/else branching)
Execute different steps based on runtime conditions.

### 2. run_if / skip_if Conditions
Add conditions to any step type to control when it executes.

### 3. Comprehensive Operators
Support for equality, comparison, membership, and emptiness checks.

### 4. Nested Path Access
Access deeply nested values using dot notation (`order.customer.status`).

---

## 1. Conditional Step Type

Execute different branches based on a condition.

### Syntax

```json
{
  "type": "conditional",
  "name": "check_order_status",
  "condition": {
    "field": "order.status",
    "operator": "equals",
    "value": "pending"
  },
  "then_step": {
    "type": "query",
    "name": "fetch_pending_details",
    "source": "postgres",
    "query": "SELECT * FROM orders WHERE status = 'pending'",
    "output": "pending_orders"
  },
  "else_step": {
    "type": "query",
    "name": "fetch_completed_details",
    "source": "postgres",
    "query": "SELECT * FROM orders WHERE status = 'completed'",
    "output": "completed_orders"
  }
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `type` | ✅ | Must be `"conditional"` |
| `name` | ❌ | Descriptive name for logging |
| `condition` | ✅ | Condition object (see below) |
| `then_step` | ❌ | Step to execute if condition is true |
| `else_step` | ❌ | Step to execute if condition is false |

### Condition Object

| Field | Required | Description |
|-------|----------|-------------|
| `field` | ✅ | Dot-notation path to value (e.g., `"order.status"`) |
| `operator` | ✅ | Comparison operator (see list below) |
| `value` | ✅* | Expected value (* not required for `is_empty`/`is_not_empty`) |

---

## 2. run_if / skip_if Conditions

Add conditional execution to **any step type**.

### run_if: Execute only if condition is true

```json
{
  "type": "query",
  "name": "expensive_query",
  "run_if": {
    "field": "user.plan",
    "operator": "equals",
    "value": "premium"
  },
  "source": "postgres",
  "query": "SELECT * FROM premium_data",
  "output": "premium_results"
}
```

**Behavior:**
- ✅ Condition true → Step executes normally
- ⏭️ Condition false → Step skipped, returns `{}`

### skip_if: Skip if condition is true

```json
{
  "type": "transform",
  "name": "process_data",
  "skip_if": {
    "field": "data",
    "operator": "is_empty"
  },
  "function": "process_results",
  "inputs": ["data"],
  "output": "processed_data"
}
```

**Behavior:**
- ⏭️ Condition true → Step skipped, returns `{}`
- ✅ Condition false → Step executes normally

---

## 3. Operators

### Equality

| Operator | Description | Example |
|----------|-------------|---------|
| `equals` | Exact match | `{"field": "status", "operator": "equals", "value": "active"}` |
| `not_equals` | Not equal | `{"field": "status", "operator": "not_equals", "value": "deleted"}` |

### String/Array Membership (Enhanced, Case-Insensitive)

| Operator | Description | Single Value | Array Values |
|----------|-------------|--------------|--------------|
| `contains` | Value(s) present in field (case-insensitive) | `"value": "pending"` | `"value": ["pending", "review"]` |
| `not_contains` | Value(s) absent from field (case-insensitive) | `"value": "error"` | `"value": ["error", "failed"]` |

**Single value examples:**
```json
// String contains (case-insensitive)
{"field": "message", "operator": "contains", "value": "success"}
// message = "Operation successful" → true
// message = "Operation SUCCESSFUL" → true

// Array contains (case-insensitive)
{"field": "tags", "operator": "contains", "value": "urgent"}
// tags = ["urgent", "customer"] → true
// tags = ["URGENT", "customer"] → true
```

**Array value examples:**
```json
// Check if ANY value is in string (case-insensitive)
{"field": "status", "operator": "contains", "value": ["pending", "processing"]}
// status = "Currently processing" → true
// status = "Currently PROCESSING" → true

// Check if ANY value is in array (case-insensitive)
{"field": "permissions", "operator": "contains", "value": ["admin", "owner"]}
// permissions = ["read", "admin"] → true
// permissions = ["read", "ADMIN"] → true

// Check if NONE of the values are in string (case-insensitive)
{"field": "result", "operator": "not_contains", "value": ["error", "failed"]}
// result = "Success" → true
// result = "ERROR occurred" → false
```

### Array Membership

| Operator | Description | Example |
|----------|-------------|---------|
| `in` | Value is in array | `{"field": "role", "operator": "in", "value": ["admin", "owner"]}` |
| `not_in` | Value not in array | `{"field": "status", "operator": "not_in", "value": ["deleted", "banned"]}` |

### Numeric Comparison

| Operator | Description | Example |
|----------|-------------|---------|
| `gt` | Greater than | `{"field": "count", "operator": "gt", "value": 10}` |
| `gte` | Greater than or equal | `{"field": "score", "operator": "gte", "value": 75}` |
| `lt` | Less than | `{"field": "price", "operator": "lt", "value": 100}` |
| `lte` | Less than or equal | `{"field": "age", "operator": "lte", "value": 18}` |

### Emptiness Check

| Operator | Description | Returns True For |
|----------|-------------|------------------|
| `is_empty` | Check if empty | `None`, `""`, `[]`, `{}`, `0`, `False` |
| `is_not_empty` | Check if not empty | Any non-empty value |

---

## 4. Nested Path Access

Access deeply nested values using dot notation.

### Examples

```json
// Simple nested object
{"field": "user.profile.name"}
// Context: {"user": {"profile": {"name": "John"}}} → "John"

// Array indexing
{"field": "orders.0.id"}
// Context: {"orders": [{"id": 123}]} → 123

// Deep nesting
{"field": "company.departments.0.employees.2.email"}
// Context: {"company": {"departments": [{"employees": [..., {..., {"email": "x@y.com"}}]}]}} → "x@y.com"
```

### Behavior

- Returns `None` if path doesn't exist
- Returns `None` if array index out of bounds
- Returns `None` if accessing property on non-dict/non-list

---

## Complete Examples

### Example 1: Order Processing Pipeline

```json
{
  "type": "data_pipeline",
  "steps": [
    {
      "type": "query",
      "name": "fetch_order",
      "source": "postgres",
      "credential_ref": "main_db",
      "query": "SELECT * FROM orders WHERE id = {order_id}",
      "output": "order"
    },
    {
      "type": "conditional",
      "name": "check_order_value",
      "condition": {
        "field": "order.total",
        "operator": "gt",
        "value": 1000
      },
      "then_step": {
        "type": "query",
        "name": "apply_premium_discount",
        "source": "postgres",
        "credential_ref": "main_db",
        "query": "SELECT apply_premium_discount({order.id})",
        "output": "discount_applied"
      },
      "else_step": {
        "type": "query",
        "name": "apply_standard_discount",
        "source": "postgres",
        "credential_ref": "main_db",
        "query": "SELECT apply_standard_discount({order.id})",
        "output": "discount_applied"
      }
    },
    {
      "type": "query",
      "name": "notify_customer",
      "run_if": {
        "field": "order.customer.email",
        "operator": "is_not_empty"
      },
      "source": "postgres",
      "credential_ref": "main_db",
      "query": "INSERT INTO notifications (email, message) VALUES ('{order.customer.email}', 'Order processed')",
      "output": "notification_sent"
    }
  ]
}
```

### Example 2: User Validation Pipeline

```json
{
  "type": "data_pipeline",
  "steps": [
    {
      "type": "query",
      "name": "fetch_user",
      "source": "postgres",
      "credential_ref": "user_db",
      "query": "SELECT * FROM users WHERE id = {user_id}",
      "output": "user"
    },
    {
      "type": "query",
      "name": "fetch_premium_data",
      "skip_if": {
        "field": "user.plan",
        "operator": "in",
        "value": ["free", "basic"]
      },
      "source": "postgres",
      "credential_ref": "user_db",
      "query": "SELECT * FROM premium_features WHERE user_id = {user_id}",
      "output": "premium_features"
    },
    {
      "type": "conditional",
      "name": "check_user_status",
      "condition": {
        "field": "user.status",
        "operator": "contains",
        "value": ["active", "trial"]
      },
      "then_step": {
        "type": "transform",
        "name": "grant_access",
        "function": "grant_user_access",
        "inputs": ["user"],
        "output": "access_granted"
      },
      "else_step": {
        "type": "transform",
        "name": "deny_access",
        "function": "deny_user_access",
        "inputs": ["user"],
        "output": "access_denied"
      }
    }
  ]
}
```

### Example 3: Enhanced Contains with Arrays

```json
{
  "type": "data_pipeline",
  "steps": [
    {
      "type": "query",
      "name": "fetch_logs",
      "source": "postgres",
      "credential_ref": "logs_db",
      "query": "SELECT * FROM logs WHERE date = CURRENT_DATE",
      "output": "logs"
    },
    {
      "type": "conditional",
      "name": "check_for_errors",
      "condition": {
        "field": "logs.message",
        "operator": "contains",
        "value": ["error", "exception", "failed", "critical"]
      },
      "then_step": {
        "type": "query",
        "name": "trigger_alert",
        "source": "postgres",
        "credential_ref": "alerts_db",
        "query": "INSERT INTO alerts (severity, message) VALUES ('high', 'Errors detected in logs')",
        "output": "alert_sent"
      }
    },
    {
      "type": "query",
      "name": "archive_clean_logs",
      "skip_if": {
        "field": "logs.tags",
        "operator": "contains",
        "value": ["urgent", "important", "review"]
      },
      "source": "postgres",
      "credential_ref": "logs_db",
      "query": "UPDATE logs SET archived = true WHERE date < CURRENT_DATE",
      "output": "logs_archived"
    }
  ]
}
```

---

## Operator Reference

### Quick Lookup Table

| Operator | Type | Supports Array Values | Case-Insensitive | Example |
|----------|------|----------------------|------------------|---------|
| `equals` | Equality | ❌ | ❌ | `status == "active"` |
| `not_equals` | Equality | ❌ | ❌ | `status != "deleted"` |
| `contains` | Membership | ✅ | ✅ | `"error" in message` or `["error","fail"] in message` |
| `not_contains` | Membership | ✅ | ✅ | `"error" not in message` or `["error","fail"] not in message` |
| `in` | Membership | ✅ (value is array) | ❌ | `role in ["admin", "owner"]` |
| `not_in` | Membership | ✅ (value is array) | ❌ | `status not in ["deleted", "banned"]` |
| `gt` | Comparison | ❌ | ❌ | `count > 10` |
| `gte` | Comparison | ❌ | ❌ | `score >= 75` |
| `lt` | Comparison | ❌ | ❌ | `price < 100` |
| `lte` | Comparison | ❌ | ❌ | `age <= 18` |
| `is_empty` | Check | ❌ | ❌ | `data is empty` |
| `is_not_empty` | Check | ❌ | ❌ | `data is not empty` |

---

## Error Handling

### Malformed Conditions
- Missing `field` or `operator` → Logs warning, defaults to executing step
- Invalid operator → Logs error, condition evaluates to `false`
- Path doesn't exist → Returns `None`, condition evaluates based on operator

### Evaluation Errors
- Type conversion errors (e.g., `gt` on non-numeric) → Logs error, returns `false`
- All errors are logged but don't crash the pipeline

---

## Best Practices

### 1. Use Descriptive Names
```json
{
  "name": "check_premium_user",  // Good
  "name": "step_1"               // Bad
}
```

### 2. Prefer `run_if` for Simple Cases
```json
// Simple: Use run_if
{"type": "query", "run_if": {...}}

// Complex: Use conditional
{"type": "conditional", "then_step": {...}, "else_step": {...}}
```

### 3. Check Emptiness Before Using
```json
{
  "type": "query",
  "run_if": {
    "field": "customer.email",
    "operator": "is_not_empty"
  },
  "query": "... WHERE email = '{customer.email}'"
}
```

### 4. Use Array Values for Multiple Options
```json
// Check for any error keywords
{
  "condition": {
    "field": "status",
    "operator": "contains",
    "value": ["error", "failed", "exception", "critical"]
  }
}
```

---

## Logging

All conditional logic is logged:

```
[ACTIONS] Pipeline step 0 (check_order_value): condition order.total gt 1000 = true (actual: 1500)
[ACTIONS] Pipeline step 0 (check_order_value): executing 'then' branch
[ACTIONS] Pipeline step 1 (notify_customer): skipped due to condition
[ACTIONS] Pipeline step 2 (check_user_status): condition user.status contains ["active", "trial"] = false (actual: "suspended")
[ACTIONS] Pipeline step 2 (check_user_status): executing 'else' branch
```

---

## Summary

✅ **Conditional branching** with `conditional` step type  
✅ **Conditional execution** with `run_if` / `skip_if` on any step  
✅ **12 operators** covering equality, comparison, membership, emptiness  
✅ **Enhanced `contains`** accepts single value or array of values  
✅ **Nested path access** with dot notation  
✅ **Deterministic execution** - no LLM required  
✅ **Error-safe** - errors are logged, don't crash pipelines  

Your data pipelines are now fully programmable! 🎉
