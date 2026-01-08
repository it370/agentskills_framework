---
name: ExternalAPIValidator
description: Call external validation API synchronously
requires:
  - document_id
  - document_type
produces:
  - validation_result
  - validation_status
  - validation_errors
executor: action

action:
  type: http_call
  url: "https://api.example.com/validate/{document_type}/{document_id}"
  method: GET
  timeout: 15.0
  headers:
    Accept: application/json
---

# ExternalAPIValidator

## Purpose
Call an external validation API synchronously and return results.
This demonstrates the `http_call` action type for simple REST API calls.

## Difference from REST Executor
- **http_call action**: Synchronous, returns immediately, no callback
- **REST executor**: Asynchronous, uses callbacks, for long-running tasks

## Use Cases for http_call
- Quick API lookups (< 15 seconds)
- Synchronous validation services
- Real-time data fetching
- Simple REST integrations

## Configuration
- **URL Template**: Supports placeholder substitution
- **Method**: GET, POST, PUT, PATCH, DELETE
- **Headers**: Custom headers for authentication/content-type
- **Timeout**: Request timeout in seconds

## Output Schema
- `validation_result`: Response body from API
- `validation_status`: HTTP status code
- `validation_errors`: Any validation errors found

## Example
Input:
```json
{
  "document_id": "DOC123",
  "document_type": "passport"
}
```

API Call:
```
GET https://api.example.com/validate/passport/DOC123
```

Output:
```json
{
  "response": {
    "valid": true,
    "score": 95,
    "checks_passed": 8,
    "checks_failed": 0
  }
}
```
