---
name: DataTransformer
description: Transform data using skill-local script
requires:
  - input_data
  - transform_type
produces:
  - transformed_data
  - transform_stats
executor: action

action:
  type: script
  script_path: transform.py
  # Relative path - resolves from this skill folder
  interpreter: python
  timeout: 30.0
---

# DataTransformer

## Purpose
Demonstrates **skill-local script execution**.

The transformation logic is in `transform.py` in the same folder.

## How It Works
1. Framework detects relative `script_path`
2. Resolves path from skill folder
3. Executes script with JSON stdin/stdout
4. Returns results to workflow

## Skill Structure
```
DataTransformer/
  ├── skill.md          # This file
  └── transform.py      # Transformation script
```

## Benefits
- **Portable**: Drop folder anywhere, it just works
- **Self-contained**: No external script dependencies
- **Language-agnostic**: Can be Python, Node.js, Ruby, etc.
- **Runtime-ready**: Add skills without restart

## Transform Types Supported
- `normalize`: Normalize data to 0-1 range
- `standardize`: Z-score standardization
- `aggregate`: Aggregate by key
- `filter`: Filter by criteria
