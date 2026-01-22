# LLM Model Selection Logic

## Overview
Strict validation system for LLM model selection with zero fallbacks. Models must be configured in database before use.

## Selection Priority

### For Skill Execution
```
1. Skill-level model (skill.llm_model)
   ↓ (if not set)
2. Run-level model (state.llm_model from /start or /rerun)
   ↓ (if not set)
3. Default model (database is_default=TRUE or env LLM_DEFAULT_MODEL)
   ↓ (if not set)
4. ERROR: No default configured
```

### For Run Initialization
```
1. Requested model (/start llm_model parameter)
   ↓ (if not set)
2. Default model (database is_default=TRUE or env LLM_DEFAULT_MODEL)
   ↓ (if not set)
3. ERROR: No default configured
```

## Validation Rules

### ✅ Valid Model
- Must exist in `llm_models` table
- Must have `is_active = TRUE`
- Must have non-empty `api_key`

### ❌ Invalid Model
- Not in database → **HTTP 400 error**
- `is_active = FALSE` → **HTTP 400 error**
- Missing/empty `api_key` → **HTTP 400 error**
- Database unreachable → **HTTP 400 error**

**NO fallbacks. NO assumptions. NO silent errors.**

## Configuration

### Required Setup
1. **Add models via `/admin/llm-models`**:
   - Provider (e.g., "openai")
   - Model name (e.g., "gpt-4o-mini")
   - API key (e.g., "sk-...")
   - Mark as Active ✓

2. **Set default** (choose one):
   - Mark one model as Default in admin UI, OR
   - Set `LLM_DEFAULT_MODEL=gpt-4o-mini` in `.env`

### Skill Configuration
```json
{
  "name": "analyze-data",
  "llm_model": "gpt-4o-mini",  // Specific model
  "llm_model": null,            // Inherit from run
  "llm_model": ""               // Inherit from run
}
```

## API Usage

### Start Run with Specific Model
```bash
POST /start
{
  "sop": "Process order",
  "llm_model": "gpt-4o-mini"  # Must be in database
}
```

### Start Run with Default Model
```bash
POST /start
{
  "sop": "Process order"
  # llm_model omitted = uses default
}
```

## Error Messages

| Scenario | Error |
|----------|-------|
| Model not in DB | `Model 'xxx' is not configured. Available: gpt-4, gpt-4o-mini` |
| No models configured | `No LLM models configured in database. Configure via /admin/llm-models` |
| Missing API key | `Model 'gpt-4' is missing API key. Add via /admin/llm-models` |
| No default set | `No default model configured. Set database default or LLM_DEFAULT_MODEL env` |

## Code References

| Function | Purpose | Location |
|----------|---------|----------|
| `_resolve_llm_model()` | Skill execution model resolution | `engine.py:547` |
| `_resolve_global_llm_model()` | Run initialization model resolution | `engine.py:566` |
| `_validate_llm_model()` | Database validation | `engine.py:456` |
| `_resolve_llm_api_key()` | API key retrieval | `engine.py:501` |
| `_default_llm_model()` | Default model lookup | `engine.py:408` |

## Examples

### Example 1: Skill Override
```
Run started with: llm_model="gpt-4"
Skill "analyze" has: llm_model="gpt-4o-mini"
Result: Skill uses "gpt-4o-mini" ✅
```

### Example 2: Skill Inherits
```
Run started with: llm_model="gpt-4"
Skill "summarize" has: llm_model=null
Result: Skill uses "gpt-4" ✅
```

### Example 3: Both Use Default
```
Run started with: llm_model not specified
Skill "process" has: llm_model=null
Default in DB: "gpt-4o-mini"
Result: Both use "gpt-4o-mini" ✅
```

### Example 4: Invalid Model Rejected
```
Run started with: llm_model="fake-model"
Result: HTTP 400 - "Model 'fake-model' is not configured" ❌
```

## Security Notes

- All API keys stored encrypted in database
- Only `system` user can manage models via `/admin/llm-models`
- Inactive models cannot be selected
- No hardcoded API keys in code
- Backend enforces validation (REST API safe)
