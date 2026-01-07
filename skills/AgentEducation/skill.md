---
name: AgentEducation
description: Extracts degree and graduation year from CV text to determine qualification.
requires:
  - cv_text
produces:
  - degree
  - grad_year
  - is_qualified
optional_produces:
  - dob
hitl_enabled: false
---

# AgentEducation

## Purpose
Read CV text and extract highest degree, graduation year, and a simple qualification flag.

## Output Schema (reference)
- degree: string
- grad_year: string
- is_qualified: boolean
- dob: string (optional)

