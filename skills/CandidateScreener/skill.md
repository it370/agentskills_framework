---
name: CandidateScreener
description: Final decision agent that combines qualification and background outcomes.
requires:
  - is_qualified
  - criminal_status
produces:
  - final_decision
  - summary
hitl_enabled: true
---

# CandidateScreener

## Purpose
Summarize findings and provide a final hire/no-hire decision with rationale.

## Output Schema (reference)
- final_decision: string
- summary: string

