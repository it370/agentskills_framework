---
name: WNFEVerifier
description: Verifies a given employment record against all the employment history (called WNFE - Work Number) of a given individual.
requires:
  - order_details
#   - order_details.employer_company_name
#   - order_details.start_date
#   - order_details.end_date
#   - order_details.job_title
#   - order_details.reason_for_leaving
produces:
  - is_match_found
  - detailed_comparison_statement
optional_produces:
  - matched_company
hitl_enabled: false
---

# WNFEVerifier

## Purpose
WNFE is a list of work history of a given candidate pulled based of of his order number which is internally mapped to candidate's SSN and other personal details. Verify candidate's claims against the work history to find match and verify accuracy.

Use this REST API for WNFE list: http://localhost:8000/mock/wnfe

## Matching Rule
A match is confirmed if company, joining start date, job title, full name and reason for leaving matches exactly as in records. Do not compare other parameters.
A company match is confirmed by following conditions:
- Names matches exactly
- Given name is an abbreviation of logbook's company name
- Treat Pvt Ltd., Org, Inc. as different companies even with similar/same names

Reaseon for leaving Rule:
  - Records may use different words, derive a semantic meaning.
  - Treat as same if the meanings are the same.

