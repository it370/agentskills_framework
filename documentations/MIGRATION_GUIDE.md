# Migration Guide: Converting LLM Skills to Action Skills

This guide helps you identify which LLM skills should be converted to action skills and how to do it.

## When to Migrate

### ✅ Good Candidates for Migration (Action)

Migrate to action executor if the skill:

1. **Performs calculations**
   - Risk scoring
   - Financial calculations
   - Statistical analysis
   - Mathematical operations

2. **Fetches data directly**
   - Database queries
   - Cache lookups
   - File reading
   - Configuration retrieval

3. **Applies business rules**
   - Validation logic
   - Approval workflows
   - Tier/category assignment
   - Status determination

4. **Transforms data**
   - Format conversion
   - Data normalization
   - Aggregation/merging
   - Filtering/mapping

5. **Calls external APIs synchronously**
   - Quick validation services
   - Real-time lookups
   - Status checks
   - Simple integrations

### ❌ Keep as LLM Executor

Keep LLM executor if the skill requires:

1. **Natural language understanding**
   - Email composition
   - Text summarization
   - Sentiment analysis
   - Intent detection

2. **Creative generation**
   - Content writing
   - Recommendations
   - Explanations
   - Personalization

3. **Complex reasoning**
   - Decision making with uncertainty
   - Multi-step analysis
   - Context-dependent logic
   - Judgment calls

4. **Unstructured data processing**
   - Resume analysis
   - Document understanding
   - Image interpretation
   - Freeform text extraction

## Migration Examples

### Example 1: Simple Calculation

**Before (LLM):**
```yaml
---
name: DiscountCalculator
executor: llm
prompt: |
  Calculate the discounted price.
  Price: {price}
  Customer type: {customer_type}
  
  Rules:
  - VIP customers get 20% off
  - Members get 10% off
  - Regular customers get no discount
  
  Return the final_price and discount_amount.
system_prompt: You are a pricing calculator.
---
```

**After (Action):**
```yaml
---
name: DiscountCalculator
executor: action
action:
  type: python_function
  module: business_logic.pricing
  function: calculate_discount
---
```

```python
# business_logic/pricing.py
from actions import action

@action(
    requires={"price", "customer_type"},
    produces={"final_price", "discount_amount"}
)
def calculate_discount(price, customer_type):
    discounts = {"vip": 0.20, "member": 0.10, "regular": 0.0}
    discount_amount = price * discounts.get(customer_type, 0.0)
    return {
        "final_price": price - discount_amount,
        "discount_amount": discount_amount
    }
```

**Benefits:**
- 200x faster (5ms vs 1000ms)
- 99% cheaper ($0.0001 vs $0.01)
- 100% reliable (no hallucinations)
- Easy to test

### Example 2: Database Query

**Before (LLM with http_request tool):**
```yaml
---
name: UserProfileFetcher
executor: llm
prompt: |
  Fetch user profile for user_id: {user_id}
  
  Use the http_request tool to call:
  http://localhost:8000/api/users/{user_id}
  
  Extract the user's name, email, and status.
---
```

**After (Action with data_query):**
```yaml
---
name: UserProfileFetcher
executor: action
action:
  type: data_query
  source: postgres
  query: "SELECT id, name, email, status FROM users WHERE id = {user_id}"
---
```

**Benefits:**
- Direct database access (no API overhead)
- 100x faster
- No LLM cost
- Type-safe results

### Example 3: Multi-Source Data Aggregation

**Before (LLM with multiple tool calls):**
```yaml
---
name: CandidateProfileEnricher
executor: llm
prompt: |
  Enrich candidate profile for candidate_id: {candidate_id}
  
  1. Call the database to get basic profile
  2. Call the documents API to get uploaded documents
  3. Call the verification API to get verification status
  4. Merge all the data together
  
  Return enriched_profile with all combined data.
---
```

**After (Action with data_pipeline):**
```yaml
---
name: CandidateProfileEnricher
executor: action
action:
  type: data_pipeline
  steps:
    - type: query
      source: postgres
      query: "SELECT * FROM candidates WHERE id = {candidate_id}"
      output: profile
    
    - type: query
      source: mongodb
      collection: documents
      filter: {candidate_id: "{candidate_id}"}
      output: documents
    
    - type: query
      source: mongodb
      collection: verifications
      filter: {candidate_id: "{candidate_id}"}
      output: verifications
    
    - type: merge
      inputs: [profile, documents, verifications]
      output: enriched_profile
---
```

**Benefits:**
- Single atomic operation
- Guaranteed execution order
- No LLM reasoning overhead
- Faster and cheaper

### Example 4: Business Rule Application

**Before (LLM):**
```yaml
---
name: LoanApprovalDecider
executor: llm
prompt: |
  Decide if loan should be approved.
  
  Credit score: {credit_score}
  Income: {income}
  Debt: {debt}
  
  Rules:
  - If credit_score >= 750 AND debt/income < 0.3: APPROVE
  - If credit_score >= 650 AND debt/income < 0.5: MANUAL_REVIEW
  - Otherwise: DENY
  
  Return decision and reason.
---
```

**After (Action):**
```yaml
---
name: LoanApprovalDecider
executor: action
action:
  type: python_function
  module: business_logic.lending
  function: decide_loan_approval
---
```

```python
from actions import action

@action(
    requires={"credit_score", "income", "debt"},
    produces={"decision", "reason"}
)
def decide_loan_approval(credit_score, income, debt):
    dti = debt / income if income > 0 else float('inf')
    
    if credit_score >= 750 and dti < 0.3:
        return {"decision": "APPROVE", "reason": "Excellent credit and low DTI"}
    elif credit_score >= 650 and dti < 0.5:
        return {"decision": "MANUAL_REVIEW", "reason": "Good credit, moderate DTI"}
    else:
        return {"decision": "DENY", "reason": "Credit or DTI concerns"}
```

**Benefits:**
- Consistent decisions
- Auditable logic
- Easy to update rules
- Unit testable

## Migration Checklist

### Step 1: Identify Candidates
- [ ] Review all LLM skills
- [ ] Identify purely computational/data-fetching skills
- [ ] Check if business rules are well-defined
- [ ] Verify no creative/reasoning required

### Step 2: Extract Business Logic
- [ ] Identify the core logic in the prompt
- [ ] Determine required inputs
- [ ] Define expected outputs
- [ ] Document business rules

### Step 3: Implement Action
- [ ] Create Python function with business logic
- [ ] Add `@action` decorator
- [ ] Write unit tests
- [ ] Verify outputs match LLM version

### Step 4: Update Skill
- [ ] Change `executor` to `action`
- [ ] Add `action` configuration
- [ ] Remove `prompt` and `system_prompt`
- [ ] Keep `requires` and `produces` same

### Step 5: Test
- [ ] Run unit tests on action function
- [ ] Test skill in workflow
- [ ] Compare outputs with LLM version
- [ ] Verify performance improvement

### Step 6: Deploy
- [ ] Update documentation
- [ ] Notify team of changes
- [ ] Monitor execution
- [ ] Gather feedback

## Common Pitfalls

### Pitfall 1: Migrating Complex Reasoning
❌ **Wrong:** Migrating skills that require judgment
```python
# This is too complex for deterministic logic
def analyze_candidate_resume(resume_text):
    # How do you code "seems qualified"?
    if "seems qualified":  # This requires LLM!
        return {"qualified": True}
```

✅ **Right:** Keep complex reasoning in LLM
```yaml
executor: llm  # Stay as LLM
prompt: "Analyze this resume and determine qualification..."
```

### Pitfall 2: Hardcoding Thresholds
❌ **Wrong:** Hardcoded values
```python
def calculate_risk(score):
    if score > 750:  # What if threshold changes?
        return "low_risk"
```

✅ **Right:** Make thresholds configurable
```python
def calculate_risk(score, thresholds=None):
    thresholds = thresholds or {"low": 750, "medium": 650}
    if score > thresholds["low"]:
        return "low_risk"
```

### Pitfall 3: Ignoring Edge Cases
❌ **Wrong:** No edge case handling
```python
def calculate_ratio(debt, income):
    return debt / income  # What if income is 0?
```

✅ **Right:** Handle edge cases
```python
def calculate_ratio(debt, income):
    if income == 0:
        return float('inf')
    return debt / income
```

## Gradual Migration Strategy

You can migrate incrementally:

### Phase 1: Low-Hanging Fruit (Week 1)
Migrate simple calculations and lookups:
- Price calculations
- Discount applications
- Simple data fetches

### Phase 2: Business Rules (Week 2)
Migrate well-defined business logic:
- Approval workflows
- Tier assignments
- Validation rules

### Phase 3: Data Operations (Week 3)
Migrate data-heavy operations:
- Multi-source aggregation
- Data transformations
- Batch processing

### Phase 4: Optimization (Week 4)
Fine-tune and optimize:
- Add caching where beneficial
- Optimize database queries
- Improve error handling

## Validation

After migration, verify:

1. **Correctness**: Outputs match LLM version
2. **Performance**: Faster execution
3. **Reliability**: No failures or errors
4. **Cost**: Reduced LLM token usage
5. **Maintainability**: Code is cleaner

## Rollback Plan

If issues arise:

1. **Quick rollback**: Change `executor` back to `llm`
2. **Keep old skill**: Rename to `SkillName_v1` before migrating
3. **A/B test**: Run both versions and compare
4. **Gradual cutover**: Use feature flags

## Success Metrics

Track these metrics post-migration:

- **Execution time**: Should decrease 10-1000x
- **Cost per execution**: Should decrease 99%+
- **Error rate**: Should stay same or decrease
- **Output consistency**: Should be 100%
- **Developer satisfaction**: Easier to maintain

## Getting Help

If you're unsure whether to migrate:

1. Check the "When to Migrate" section above
2. Review example migrations in this guide
3. Run both versions and compare results
4. Ask: "Does this require creative thinking?" → Keep as LLM
5. Ask: "Is this pure logic/calculation?" → Migrate to action

## Summary

✅ **Migrate to actions:**
- Calculations and business rules
- Data fetching and transformations
- Deterministic logic
- Well-defined workflows

❌ **Keep as LLM:**
- Natural language tasks
- Creative generation
- Complex reasoning
- Unstructured data understanding

The goal is not to migrate everything, but to use the right executor for each task!
